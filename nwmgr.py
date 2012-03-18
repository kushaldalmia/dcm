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
            self.neighbors[n] = 0
            self.conn[n] = createConn(n)
        self.available = []
        self.port = localPort
        self.localIP = getLocalIP()
        self.nodeId = 8
        self.seqno = 1
        self.ttl = 32

    def createNewMessage(self, msgType, data):
        msg = str(self.nodeId) + "-" + str(self.seqno) + "-" + str(self.ttl) + "-" + msgType + "-" + data
        self.seqno += 1
        return msg

    def sendToNeighbors(self, msg):
        for key in self.conn:
            self.conn[key].send(msg)

    def startManager(self):
        initMsg = self.createNewMessage("NEIGHBOR_INIT", (self.localIP + ":" + str(self.port)))
        self.sendToNeighbors(initMsg)
        server = socket(AF_INET, SOCK_STREAM)
        server.bind(('', self.port))
        server.listen(5)
        while True:
            client, addr = server.accept()
            self.handleMessage(client.recv(4096))
        
    def handleMessage(self, msgStr):
        print "Received : " + msgStr
        msg = Message(msgStr)
        if msg.type == "NEIGHBOR_INIT":
            self.neighbors[msg.data] = 0
            self.conn[msg.data] = createConn(msg.data)
            print "Added new node to neighbor " + msg.data
        elif msg.type == "HEARTBEAT":
            # Handle HeartBeat Message
            pass
        elif msg.type == "RES_AVL":
            # Handle Resource Available Message
            pass
        elif msg.type == "RES_UNAVL":
            # Handle Resource Unavailable Message
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
 
def main():
    mgr = nwManager(int(sys.argv[1]), [])
    mgr.startManager()

if __name__ == "__main__":
    main()
