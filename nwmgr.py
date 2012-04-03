import json
import requests
import sys
import os
import time
from message import *
from socket import *
import SocketServer
import threading
import ConfigParser

def connHandler(manager, client):
    while True:
        try:
            data = client.recv(int(manager.config['buflen']))
            manager.handleMessage(data, client)
        except:
            return

def acceptConn(manager, server):
    manager.hbtTimer = threading.Timer(int(manager.config['heartbeattimeout']), sendHeartBeats, args=(manager,))
    manager.hbtTimer.start()
    while True:
        try:
            client, addr = server.accept()
            t = threading.Thread(target=connHandler, args=(manager, client,))
            t.start()
        except:
            if manager.destroy == True:
                return

def sendHeartBeats(manager):
    hbtMsg = manager.createNewMessage("HEARTBEAT", (manager.localIP + ":" + str(manager.port)))
    manager.sendToNeighbors(hbtMsg)
    manager.hbtTimer.cancel()
    manager.hbtTimer = threading.Timer(int(manager.config['heartbeattimeout']), sendHeartBeats, args=(manager,))
    manager.hbtTimer.start()

def handleTimeout(manager, node):
    manager.lock.acquire()
    timer, count = manager.neighbors[node]
    manager.lock.release()
    if manager.destroy == True:
        timer.cancel()
        return
    
    if count > int(manager.config['retrycount']):
        print "Sending RES_UNAVL for node " + node + "!"
        timer.cancel()
        manager.lock.acquire()
        manager.conn[node].close()
        del manager.neighbors[node]
        del manager.conn[node]
        manager.lock.release()
        nodefailMsg = manager.createNewMessage("RES_UNAVL", node)
        manager.sendToNeighbors(nodefailMsg)
        remove_node(manager.localIP, manager.port, node.split(":")[0],
                    node.split(":")[1], manager.config['serverip'] + ':' +
                    manager.config['serverport'])
    else:
        print "No Heartbeat from neighbor " + node + "!"
        timer.cancel()
        timer = threading.Timer(int(manager.config['heartbeattimeout']), handleTimeout, args=(manager, node,))
        timer.start()
        manager.lock.acquire()
        manager.neighbors[node] = (timer, count + 1)
        manager.lock.release()

class nwManager:
    def __init__(self, localPort, neighborList, config):
        self.neighbors = {}
        self.conn = {}
        self.lock = threading.Lock()
        self.config = config
        for n in neighborList:
            print "Neighbor is: " + n
            self.conn[n] = createConn(n)
            aliveTimer = threading.Timer(int(self.config['alivetimeout']),handleTimeout, args=(self, n,))
            aliveTimer.start()
            self.neighbors[n] = (aliveTimer,0)
            t = threading.Thread(target=connHandler, args=(self, self.conn[n],))
            t.start()
        self.available = []
        self.port = localPort
        self.localIP = getLocalIP()
        self.seqno = 1
        self.ttl = config['ttl']
        self.destroy = False

    def startManager(self):
        curTime = time.time()
        initMsg = self.createNewMessage("NEIGHBOR_INIT", (self.localIP + ":" + str(self.port)))
        self.sendToNeighbors(initMsg)

        # Initalize listening socket
        self.server = socket(AF_INET, SOCK_STREAM)
        self.server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.server.bind(('', self.port))
        self.server.listen(5)
        self.server.settimeout(1.0)

        t = threading.Thread(target=acceptConn, args=(self, self.server,))
        t.start()

    def destroyManager(self):
        self.lock.acquire()
        for key in self.conn:
            self.conn[key].close()
        self.lock.release()
        self.server.close()
        self.destroy = True

    def sendToNeighbors(self, msg):
        self.lock.acquire()
        for key in self.conn:
            try:
                self.conn[key].send(msg)
            except:
                pass
        self.lock.release()

    def handleMessage(self, msgStr, client):
        if len(msgStr) == 0:
            return
        self.lock.acquire()
        msg = Message(msgStr)
        print "Received : " + msgStr
        curTime = time.time()

        if msg.type == "NEIGHBOR_INIT":
            aliveTimer = threading.Timer(int(self.config['alivetimeout']),handleTimeout, args=(self, msg.data,))
            aliveTimer.start()
            self.neighbors[msg.data] = (aliveTimer, 0)
            self.conn[msg.data] = client
            print "Added new node to neighbor " + msg.data

        elif msg.type == "HEARTBEAT":
            self.lock.acquire()
            aliveTimer, count = self.neighbors[msg.data]
            aliveTimer.cancel()
            aliveTimer = threading.Timer(int(self.config['alivetimeout']),handleTimeout, args=(self, msg.data,))
            aliveTimer.start()
            self.neighbors[msg.data] = (aliveTimer, 0)
            self.lock.release()

        elif msg.type == "RES_AVL":
            # Handle Resource Available Message
            pass

        elif msg.type == "RES_UNAVL":
            msg.ttl -= 1
            if msg.ttl == 0:
                return
            # Handle Resource Unavailable Message
            self.sendExceptSource(msg.toString(), msg.sender)

        self.lock.release()

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

def ConfigSectionMap(config, section):
    dict1 = {}
    options = config.options(section)
    for option in options:
        try:
            dict1[option] = config.get(section, option)
            if dict1[option] == -1:
                DebugPrint("skip: %s" % option)
        except:
            print("exception on %s!" % option)
            dict1[option] = None

    return dict1
