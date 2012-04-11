import json
import requests
import sys
import os
import time
import traceback,tempfile
from message import *
from socket import *
import SocketServer
import threading
import ConfigParser
from sendfile import sendfile
from job import *

def connHandler(manager, client):
    while True:
        try:
            data = client.recv(int(manager.config['buflen']))
            if manager.handleMessage(data, client) == False:
                return
        except Exception, e:
            print "Exception:%s" % e
            manager.lock.release()
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
    manager.lock.acquire()
    freeList = ""
    for node in manager.freeNodes:
        freeList += (node + ",")
    hbtMsg = manager.createNewMessage("HEARTBEAT", freeList)
    manager.sendToNeighbors(hbtMsg)
    manager.lock.release()
    manager.hbtTimer = threading.Timer(int(manager.config['heartbeattimeout']), sendHeartBeats, args=(manager,))
    manager.hbtTimer.start()

def handleTimeout(manager, node):
    manager.lock.acquire()
    timer, count = manager.neighbors[node]
    if manager.destroy == True:
        manager.lock.acquire()
        return

    if count > int(manager.config['retrycount']):
        print "Sending RES_UNAVL for node " + node + "!"
        manager.conn[node].close()
        del manager.neighbors[node]
        del manager.conn[node]
        nodefailMsg = manager.createNewMessage("RES_UNAVL", node)
        manager.sendToNeighbors(nodefailMsg)
        remove_node(manager.localIP, manager.port, node.split(":")[0],
                    node.split(":")[1], manager.config['serverip'] + ':' +
                    manager.config['serverport'])
    else:
        print "No Heartbeat from neighbor " + node + "!"
        timer = threading.Timer(int(manager.config['alivetimeout']), handleTimeout, args=(manager, node,))
        timer.start()
        manager.neighbors[node] = (timer, count + 1)
    manager.lock.release()

class nwManager:
    def __init__(self, localPort, neighborList, jobmgr):
        self.neighbors = {}
        self.conn = {}
        self.lock = threading.Lock()

        # Read the config file
        config = ConfigParser.ConfigParser()
        config.read('config.cfg')
        nwMgrConfig = ConfigSectionMap(config, "NetworkManager")
        self.config = nwMgrConfig

        for n in neighborList:
            print "Neighbor is: " + n
            self.conn[n] = createConn(n)
            aliveTimer = threading.Timer(int(self.config['alivetimeout']),handleTimeout, args=(self, n,))
            aliveTimer.start()
            self.neighbors[n] = (aliveTimer,0)
            t = threading.Thread(target=connHandler, args=(self, self.conn[n],))
            t.start()
        self.freeNodes = []
        self.port = localPort
        self.localIP = getLocalIP()
        self.localNodeId = self.localIP + ":" + str(self.port)
        self.seqno = 1
        self.ttl = self.config['ttl']
        self.destroy = False
        self.jobmgr = jobmgr
        self.tempdir = tempfile.mkdtemp()

    def startManager(self):
        curTime = time.time()
        initMsg = self.createNewMessage("NEIGHBOR_INIT", self.localNodeId)
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
        for key in self.conn:
            try:
                self.conn[key].send(msg)
            except:
                pass

    def makeAvailable(self):
        avlMsg = self.createNewMessage("RES_AVL", self.localNodeId)
        self.lock.acquire()
        self.freeNodes.append((self.localIP + ":" + str(self.port)))
        self.sendToNeighbors(avlMsg)
        self.lock.release()

    def makeUnavailable(self):
        unavlMsg = self.createNewMessage("RES_UNAVL", self.localNodeId)
        self.lock.acquire()
        self.freeNodes.remove((self.localIP + ":" + str(self.port)))
        self.sendToNeighbors(unavlMsg)
        self.lock.release()

    def handleMessage(self, msgStr, client):
        if len(msgStr) == 0:
            return False
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
            aliveTimer, count = self.neighbors[msg.src]
            aliveTimer.cancel()
            if len(msg.data) > 0:
                freeList = msg.data.split(",")
                for node in freeList:
                    if len(node) > 0 and node not in self.freeNodes:
                        self.freeNodes.append(node)
            aliveTimer = threading.Timer(int(self.config['alivetimeout']),handleTimeout, args=(self, msg.src,))
            aliveTimer.start()
            self.neighbors[msg.src] = (aliveTimer, 0)

        elif msg.type == "RES_AVL":
            if msg.data not in self.freeNodes:
                self.freeNodes.append(msg.data)
            msg.ttl -= 1
            if msg.ttl != 0:
                # Handle Resource Unavailable Message
                self.sendExceptSource(msg.toString(), msg.src)

        elif msg.type == "RES_UNAVL":
            # TODO: Handle case when node was running job; Reschedule Job
            if msg.data in self.freeNodes:
                self.freeNodes.remove(msg.data)
            if self.jobmgr.status == 'RESERVED' and self.jobmgr.reservedBy == msg.data:
                self.jobmgr.status = 'AVAILABLE'
                self.jobmgr.reservedBy = None
            msg.ttl -= 1
            if msg.ttl != 0:
                # Handle Resource Unavailable Message
                self.sendExceptSource(msg.toString(), msg.src)

        elif msg.type == "RESERVE_REQ":
            reserved = False
            if self.jobmgr.status == 'AVAILABLE':
                ackMsg = self.createNewMessage("ACK", self.localNodeId)
                reserved = True
            else:
                ackMsg = self.createNewMessage("NACK", self.localNodeId)
            try:
                client.send(ackMsg)
                if reserved == True:
                    self.jobmgr.status = 'RESERVED'
                    self.jobmgr.reservedBy = msg.data
            except:
                pass
            client.close()
            self.lock.release()
            return False

        elif msg.type == "RELEASE_REQ":
            if self.jobmgr.status == 'RESERVED':
                self.jobmgr.status = 'AVAILABLE'
            client.close()
            self.lock.release()
            return False

        elif msg.type == "JOB_CODE":
            self.lock.release()
            self.getJob(client, msg)
            self.jobmgr.runJob()
            return False

        self.lock.release()
        return True

    def createNewMessage(self, msgType, data):
        msg = self.localNodeId + "-" + str(self.seqno) + "-" + str(self.ttl) + "-" + msgType + "-" + data
        self.seqno += 1
        return msg

    def sendExceptSource(self, msg, src):
        for key in self.conn:
            if key == src:
                continue
            try:
                self.conn[key].send(msg)
            except:
                pass

    def reserveNodes(self, num):
        # Locking required to allow more nodes to become available while reservation happens
        self.lock.acquire()
        if len(self.freeNodes) < num:
            self.lock.release()
            return False
        # Create copy of current free nodes
        freeList = self.freeNodes[:]
        self.lock.release()

        reqMsg = self.createNewMessage("RESERVE_REQ", self.localNodeId)
        for node in freeList:
            try:
                print "Sending RESERVE_REQ to node: " + node
                sock = createConn(node)
                sock.settimeout(5.0)
                sock.send(reqMsg)
                data = sock.recv(int(self.config['buflen']))
                sock.close()
                msg = Message(data)
                if msg.type == "ACK":
                    newNode = {}
                    newNode['id'] = node
                    newNode['state'] = -1
                    self.jobmgr.reservedNodes.append(newNode)
                    if len(self.jobmgr.reservedNodes) == num:
                        break
            except:
                pass

        if len(self.jobmgr.reservedNodes) == num:
            return True
        else:
            relMsg = self.createNewMessage("RELEASE_REQ", self.localNodeId)
            for node in self.jobmgr.reservedNodes:
                print "Sending RELEASE_REQ to node: " + node
                try:
                    sock = createConn(node['id'])
                    sock.settimeout(5.0)
                    sock.send(relMsg)
                    sock.close()
                except:
                    pass

            self.jobmgr.reservedNodes = []
            return False

    def sendFile(self, sock, filename):
        srcfile = open(filename, "rb")
        offset = 0
        while True:
            sent = sendfile(sock.fileno(), srcfile.fileno(), offset, 65536)
            if sent == 0:
                break
            offset += sent
        srcfile.close()
    
    def recvFile(self, sock, filename, size):
        fileObj = open(filename, 'w')
        offset = 0
        while True:
            data = sock.recv(int(self.config['buflen']))
            if len(data) == 0:
                break
            fileObj.write(data)
            offset += len(data)
            if offset >= size:
                break
        fileObj.close()

    def waitForAck(self, sock, index, statusQueue):
        data = sock.recv(int(self.config['buflen']))
        reply = Message(data)
        if reply.type == 'NACK':
            statusQueue.put(str(index) + ":" + "-2")
            return False
        return True

    def scheduleJob(self, job, index, statusQueue):
        node = self.jobmgr.reservedNodes[index]['id']
        try:
            sock = createConn(node)
            codeSize = os.stat(job.srcFile).st_size
            codeMsg = self.createNewMessage("JOB_CODE", str(codeSize))
            sock.send(codeMsg)
            if self.waitForAck(sock, index, statusQueue) == False: return
            
            self.sendFile(sock, job.srcFile)
            if self.waitForAck(sock, index, statusQueue) == False: return

            dataSize = os.stat("chunk" + str(index)).st_size
            dataMsg = self.createNewMessage("JOB_DATA", str(dataSize))
            sock.send(dataMsg)
            if self.waitForAck(sock, index, statusQueue) == False: return
            
            self.sendFile(sock, "chunk" + str(index))
            if self.waitForAck(sock, index, statusQueue) == False: return

            statusQueue.put(str(index) + ":" + str(index))
            sock.close()

        except Exception, e:
            print "Exception in Job Schedule:%s" % e
            traceback.print_exc()
            statusQueue.put(str(index) + ":" + "-2")
            sock.close()
            return

    def getJob(self, sock, msg):
        try:
            ackMsg = self.createNewMessage("ACK", "")
            sock.send(ackMsg)
            codeSize = int(msg.data)
            codeFile = os.path.join(self.tempdir, "script.py")
            dataFile = os.path.join(self.tempdir, "data.txt")
            opFile = os.path.join(self.tempdir, "op.txt")
            print codeFile
            self.recvFile(sock, codeFile, codeSize)
            os.chmod(codeFile, 0777)
            sock.send(ackMsg)
            data = sock.recv(int(self.config['buflen']))
            msg = Message(data)
            if msg.type != "JOB_DATA":
                return
            sock.send(ackMsg)
            dataSize = int(msg.data)
            self.recvFile(sock, dataFile, dataSize)
            sock.send(ackMsg)
            job = Job(dataFile, codeFile, opFile, 0)
            job.owner = msg.src
            self.jobmgr.curJob = job
            sock.close()

        except Exception, e:
            print "Exception in getJob: %s" % e
            traceback.print_exc()
            sock.close()
        return


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
