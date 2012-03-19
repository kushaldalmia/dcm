import sys
import os
import time
from message import *
from socket import *
import SocketServer
import threading

def connHandler(manager, client):
    while True:
        try:
            data = client.recv(4096)
            if manager.handleMessage(data, client) == False:
                # Remove conn from manager neighbor list
                return
        except:
            pass

def acceptConn(manager, server):
    manager.hbtTimer = threading.Timer(10, sendHeartBeats, args=(manager,))
    manager.hbtTimer.start()
    while True:
        client, addr = server.accept()
        t = threading.Thread(target=connHandler, args=(manager, client,))
        t.start()

def sendHeartBeats(manager):
    hbtMsg = manager.createNewMessage("HEARTBEAT", (manager.localIP + ":" + str(manager.port)))
    manager.sendToNeighbors(hbtMsg)
    manager.hbtTimer.cancel()
    manager.hbtTimer = threading.Timer(10, sendHeartBeats, args=(manager,))
    manager.hbtTimer.start()

def handleTimeout(manager, node):
    timer, count = manager.neighbors[node]
    if count > 2:
        print "Send RES_UNAVL!"
    else:
        print "No Heartbeat from neighbor!"
        timer.cancel()
        timer = threading.Timer(10,handleTimeout, args=(manager, node,))
        timer.start()
        manager.neighbors[node] = (timer, count + 1)

class nwManager:
    def __init__(self, localPort, neighborList, nodeId):
        self.neighbors = {}
        self.conn = {}
        for n in neighborList:
            self.conn[n] = createConn(n)
            aliveTimer = threading.Timer(10,handleTimeout, args=(self, n,))
            aliveTimer.start()
            self.neighbors[n] = (aliveTimer,0)
            t = threading.Thread(target=connHandler, args=(self, self.conn[n],))
            t.start()
        self.available = []
        self.port = localPort
        self.localIP = getLocalIP()
        self.nodeId = nodeId
        self.seqno = 1
        self.ttl = 32

    def startManager(self):
        curTime = time.time()
        initMsg = self.createNewMessage("NEIGHBOR_INIT", (self.localIP + ":" + str(self.port)))
        self.sendToNeighbors(initMsg)
               
        # Initalize listening socket
        server = socket(AF_INET, SOCK_STREAM)
        server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        server.bind(('', self.port))
        server.listen(5)

        t = threading.Thread(target=acceptConn, args=(self, server,))
        t.start()

        
    def sendToNeighbors(self, msg):
        for key in self.conn:
            try:
                self.conn[key].send(msg)
            except:
                pass

    def handleMessage(self, msgStr, client):
        if len(msgStr) == 0:
            return True
        msg = Message(msgStr)
        print "Received : " + msgStr
        curTime = time.time()

        if msg.type == "NEIGHBOR_INIT":
            aliveTimer = threading.Timer(10,handleTimeout, args=(self, msg.data,))
            aliveTimer.start()
            self.neighbors[msg.data] = (aliveTimer, 0)
            self.conn[msg.data] = client
            print "Added new node to neighbor " + msg.data

        elif self.neighbors[msg.data] == None:
            return False

        elif msg.type == "HEARTBEAT":
            aliveTimer, count = self.neighbors[msg.data]
            aliveTimer.cancel()
            aliveTimer = threading.Timer(10,handleTimeout, args=(self, msg.data,))
            aliveTimer.start()
            self.neighbors[msg.data] = (aliveTimer, 0)

        elif msg.type == "RES_AVL":
            # Handle Resource Available Message
            pass

        elif msg.type == "RES_UNAVL":
            # Handle Resource Unavailable Message
            pass
        return True
            
    
    def createNewMessage(self, msgType, data):
        msg = str(self.nodeId) + "-" + str(self.seqno) + "-" + str(self.ttl) + "-" + msgType + "-" + data
        self.seqno += 1
        return msg


# Helper Routines
def createConn(n):
    sock = socket(AF_INET, SOCK_STREAM)
    neighborIP = n.split(":")[0]
    (neighborHostname,alias,addrlist) = gethostbyaddr(neighborIP)
    neighborPort = int(n.split(":")[1])
    sock.connect((neighborHostname, neighborPort))
    return sock

def getLocalIP():
    s = socket(AF_INET, SOCK_DGRAM)
    s.connect(('google.com', 0))
    return s.getsockname()[0]
 
def main():
    mgr = nwManager(int(sys.argv[1]), [], 1)
    mgr.startManager()
    while True:
        continue

if __name__ == "__main__":
    main()
