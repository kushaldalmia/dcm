import sys
import os
import time
from message import *
from socket import *
import SocketServer

class nwManager:

    def __init__(self, localPort, neighborList):
        self.neighbors = {}
        self.conn = {}
        for n in neighborList:
            self.neighbors[n] = (0,0)
            self.conn[n] = createConn(n)
        self.available = []
        self.port = localPort
        self.localIP = getLocalIP()
        self.nodeId = 8
        self.seqno = 1
        self.ttl = 32
        self.heartbeatTime = 0.0

    def createNewMessage(self, msgType, data):
        msg = str(self.nodeId) + "-" + str(self.seqno) + "-" + str(self.ttl) + "-" + msgType + "-" + data
        self.seqno += 1
        return msg

    def sendToNeighbors(self, msg):
        for key in self.conn:
            self.conn[key].send(msg)

    def startManager(self):
        curTime = time.time()
        initMsg = self.createNewMessage("NEIGHBOR_INIT", (self.localIP + ":" + str(self.port)))
        self.sendToNeighbors(initMsg)
        for key in self.neighbors:
            self.neighbors[key] = (curTime, 0)
        self.heartbeatTime = curTime
        
        # Initalize listening socket
        server = socket(AF_INET, SOCK_STREAM)
        server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        server.bind(('', self.port))
        server.listen(5)
        server.settimeout(1)

        # Main Server Loop
        while True:
            try:
                client, addr = server.accept()
                self.handleMessage(client.recv(4096))
            except:
                pass
            self.handleTimeouts()
            self.sendHeartBeats()            
        
    def handleMessage(self, msgStr):
        print "Received : " + msgStr
        msg = Message(msgStr)
        curTime = time.time()
        if msg.type == "NEIGHBOR_INIT":
            self.neighbors[msg.data] = (curTime, 0)
            self.conn[msg.data] = createConn(msg.data)
            print "Added new node to neighbor " + msg.data
        elif msg.type == "HEARTBEAT":
            self.neighbors[msg.data] = (curTime, 0)
        elif msg.type == "RES_AVL":
            # Handle Resource Available Message
            pass
        elif msg.type == "RES_UNAVL":
            # Handle Resource Unavailable Message
            pass
    
    def handleTimeouts(self):
        curTime = time.time()
        for n in self.neighbors:
            timestamp, count = self.neighbors[n]
            if curTime - timestamp > 10.0:
                if count == 2:
                    print "Node " + n + "Failed!"
                    # Send RES_UNAVL if resource was available
                else:
                    print "No Heartbeat from " + n
                    neighbors[n] = (curTime, count + 1)
            
    def sendHeartBeats(self):
        curTime = time.time()
        if curTime - self.heartbeatTime > 10.0:
            hbtMsg = self.createNewMessage("HEARTBEAT", (self.localIP + ":" + str(self.port)))
            self.sendToNeighbors(hbtMsg)
            self.heartbeatTime = curTime
        

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
    mgr = nwManager(int(sys.argv[1]), [])
    mgr.startManager()

if __name__ == "__main__":
    main()
