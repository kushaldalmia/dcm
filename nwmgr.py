import sys
import os
import time
from message import *
import SocketServer

class RequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        self.data = self.request.recv(1024)
        print "Received : " + self.data
        msg = Message(self.data)
        

# To initialize a nwManager, it should be passed the local port and a list of neighbors of the form "IP:Port"
class nwManager:

    def __init__(self, localPort, neighborList):
        curTime = str(time.time())
        self.neighbors = {}
        for n in neighborList:
            self.neighbors[n] = curTime
        self.available = []
        self.port = localPort

    def start(self):
        server = SocketServer.TCPServer(("localhost", self.port), RequestHandler)
        server.serve_forever()       
 
def main():
    mgr = nwManager(1337, "")
    mgr.start()

if __name__ == "__main__":
    main()
