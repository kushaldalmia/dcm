import json
import requests
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
            manager.handleMessage(data, client)
        except:
            return
            
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
    manager.lock.acquire()
    timer, count = manager.neighbors[node]
    if count > 2:
        print "Sending RES_UNAVL for node " + node + "!"
        timer.cancel()
        del manager.neighbors[node]
        del manager.conn[node]
        nodefailMsg = manager.createNewMessage("RES_UNAVL", node)
        manager.sendToNeighbors(nodefailMsg)
        remove_node(self.localIP, self.port, node.split(":")[0], node.split(":")[1], "128.237.127.109:5000")
    else:
        print "No Heartbeat from neighbor " + node + "!"
        timer.cancel()
        timer = threading.Timer(10,handleTimeout, args=(manager, node,))
        timer.start()
        manager.neighbors[node] = (timer, count + 1)
    manager.lock.release()

class nwManager:
    def __init__(self, localPort, neighborList):
        self.neighbors = {}
        self.conn = {}
        self.lock = threading.Lock()
        for n in neighborList:
            print "Neighbor is: " + n
            self.conn[n] = createConn(n)
            aliveTimer = threading.Timer(10,handleTimeout, args=(self, n,))
            aliveTimer.start()
            self.neighbors[n] = (aliveTimer,0)
            t = threading.Thread(target=connHandler, args=(self, self.conn[n],))
            t.start()
        self.available = []
        self.port = localPort
        self.localIP = getLocalIP()
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
            return
        msg = Message(msgStr)
        print "Received : " + msgStr
        curTime = time.time()

        if msg.type == "NEIGHBOR_INIT":
            self.lock.acquire()
            aliveTimer = threading.Timer(10,handleTimeout, args=(self, msg.data,))
            aliveTimer.start()
            self.neighbors[msg.data] = (aliveTimer, 0)
            self.conn[msg.data] = client
            self.lock.release()
            print "Added new node to neighbor " + msg.data

        elif msg.type == "HEARTBEAT":
            self.lock.acquire()
            aliveTimer, count = self.neighbors[msg.data]
            aliveTimer.cancel()
            aliveTimer = threading.Timer(10,handleTimeout, args=(self, msg.data,))
            aliveTimer.start()
            self.neighbors[msg.data] = (aliveTimer, 0)
            self.lock.release()

        elif msg.type == "RES_AVL":
            # Handle Resource Available Message
            pass

        elif msg.type == "RES_UNAVL":
            # Handle Resource Unavailable Message
            self.sendExceptSource(msg.toString(), msg.sender)            
    
    def createNewMessage(self, msgType, data):
        msg = str(self.localIP + ":" + str(self.port)) + "-" + str(self.seqno) + "-" + str(self.ttl) + "-" + msgType + "-" + data
        self.seqno += 1
        return msg

    def sendExceptSource(self, msg, node):
        for key in self.conn:
            if key == node:
                continue
            try:
                self.conn[key].send(msg)
            except:
                pass


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
 
def register_node(localIP, localPort, server):
    data = requests.get("http://" + server + "/register/" + str(localIP) + "/" + str(localPort))
    ip_list = json.loads(data.text)
    ip_list = ip_list[1:]
    neighbor_list = []
    for info in ip_list:
        neighbor_list.append(str(info['ip_add']) + ":" + str(info['port']))
    return neighbor_list

def remove_node(localIP, localPort, nodeIP, nodePort, server):
    data = requests.get("http://" + server + "/unregister/" + str(localIP) + "/" + str(localPort) + "/" + str(nodeIP) + "/" + str(nodePort));

def main():
    neighbor_list = register_node(getLocalIP(), sys.argv[1], "128.237.127.109:5000")
    mgr = nwManager(int(sys.argv[1]), neighbor_list)
    mgr.startManager()
    while True:
        continue

if __name__ == "__main__":
    main()
