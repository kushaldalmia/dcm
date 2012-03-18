import sys
import os
import time
from message import *
from socket import *
import SocketServer

class RequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        self.data = self.request.recv(1024)
        print "Received : " + self.data
        msg = Message(self.data)
        

class nwManager:

    def __init__(self, localPort, neighborList):
        self.neighbors = {}
        self.conn = {}
        for n in neighborList:
            self.neighbors[n] = 0
            self.conn[n] = socket(AF_INET, SOCK_STREAM)
            neighborIP = n.split(":")[0]
            neighborHostname = gethostbyaddr(neighborIP)
            neighborPort = int(n.split(":")[1])
            self.conn[n].connect(neighborHostname, neighborPort)
        self.available = []
        self.port = localPort
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

    def start(self):
        initMsg = self.createNewMessage("NEIGHBOR_CONN", ("127.0.0.1:" + str(self.port)))
        self.sendToNeighbors(initMsg)
        server = SocketServer.TCPServer(("localhost", self.port), RequestHandler)
        server.serve_forever()       
 
def main():
    mgr = nwManager(1337, "")
    mgr.start()

if __name__ == "__main__":
    main()
