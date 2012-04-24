import json
import requests
import sys
import os
import time
from cpuinfo import *
import traceback,tempfile
from message import *
from socket import *
import SocketServer
import threading
import ConfigParser
import psutil
from sendfile import sendfile
from job import *

MSG_LEN_FIELD = 5

def recvMessage(sock):
    msgLen = sock.recv(MSG_LEN_FIELD)
    if len(msgLen) == 0:
        return ''
    msgLen = int(msgLen[:4])
    data = sock.recv(msgLen)
    return data

def connHandler(manager, client):
    while True:
        try:
            data = recvMessage(client)
            if manager.handleMessage(data, client) == False:
                return
        except Exception, e:
            print "Exception:%s" % e
            traceback.print_exc()
            return

def acceptConn(manager, server):
    manager.hbtTimer = threading.Timer(int(manager.config['heartbeattimeout']), sendHeartBeats, args=(manager,))
    manager.hbtTimer.start()
    manager.updateTimer = threading.Timer(int(manager.config['updatetimeout']), sendUpdates, args=(manager,))
    manager.updateTimer.start()
    while True:
        try:
            client, addr = server.accept()
            t = threading.Thread(target=connHandler, args=(manager, client,))
            t.start()
        except:
            if manager.destroy == True:
                return

def sendUpdates(manager):
    manager.lock.acquire()
    freeList = ""
    for node in manager.freeNodes:
        freeList += (node + ",")
    updateMsg = manager.createNewMessage("UPDATE", freeList)
    manager.sendToNeighbors(updateMsg)
    manager.lock.release()
    manager.updateTimer = threading.Timer(int(manager.config['updatetimeout']), sendUpdates, args=(manager,))
    manager.updateTimer.start()

def sendHeartBeats(manager):
    manager.lock.acquire()
    hbtMsg = manager.createNewMessage("HEARTBEAT", "")
    manager.sendToNeighbors(hbtMsg)
    manager.lock.release()
    manager.hbtTimer = threading.Timer(int(manager.config['heartbeattimeout']), sendHeartBeats, args=(manager,))
    manager.hbtTimer.start()

def handleTimeout(manager, node):
    manager.lock.acquire()
    if manager.destroy == True or node not in manager.neighbors:
        manager.lock.release()
        return
    timer, count = manager.neighbors[node]
    if count > int(manager.config['retrycount']):
        print "Sending RES_UNAVL for node " + node + "!"
        manager.conn[node].close()
        del manager.neighbors[node]
        del manager.conn[node]
        nodefailMsg = manager.createNewMessage("RES_UNAVL", node)
        manager.sendToNeighbors(nodefailMsg)
        result = remove_node(manager.localIP, manager.port, node.split(":")[0],
                             node.split(":")[1], manager.config['serverip'])

        if result != '':
            manager.sendNeighborInitMsg(result)

        #TODO: Move to new function
        if node in manager.freeNodes:
            manager.freeNodes.remove(node)
        if manager.jobmgr.status == 'JOBEXEC':
            if node in manager.jobmgr.reservedNodes and manager.jobmgr.reservedNodes[node] >= 0:
                    manager.jobmgr.unScheduledQueue.put(manager.jobmgr.reservedNodes[node])
                    del manager.jobmgr.reservedNodes[node]
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
            try:
                self.conn[n] = createConn(n)
                aliveTimer = threading.Timer(int(self.config['alivetimeout']),handleTimeout, args=(self, n,))
                aliveTimer.start()
                self.neighbors[n] = (aliveTimer,0)
                t = threading.Thread(target=connHandler, args=(self, self.conn[n],))
                t.start()
            except:
                pass
        self.freeNodes = []
        self.port = localPort
        self.localIP = getLocalIP()
        self.localNodeId = self.localIP + ":" + str(self.port)
        self.seqno = 1
        self.ttl = self.config['ttl']
        self.destroy = False
        self.jobmgr = jobmgr

    def startManager(self):
        curTime = time.time()
        initMsg = self.createNewMessage("NEIGHBOR_INIT", self.localNodeId)
        self.sendToNeighbors(initMsg)

        # Initalize listening socket
        self.server = socket(AF_INET, SOCK_STREAM)
        self.server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.server.bind(('', self.port))
        self.server.listen(5)
        # Timeout required to check every one sec if node has to be destroyed
        self.server.settimeout(1.0)

        t = threading.Thread(target=acceptConn, args=(self, self.server,))
        t.start()

    def destroyManager(self):
        self.lock.acquire()
        for key in self.conn:
            self.conn[key].close()
        self.lock.release()
        disconnect_node(self.localIP, self.port, self.config['serverip']) 
        self.server.close()
        self.destroy = True

    def sendNeighborInitMsg(self, node):
        try:
            if node in self.neighbors:
                return
            self.conn[node] = createConn(node)
            aliveTimer = threading.Timer(int(self.config['alivetimeout']),handleTimeout, args=(self, node,))
            aliveTimer.start()
            self.neighbors[node] = (aliveTimer,0)
            t = threading.Thread(target=connHandler, args=(self, self.conn[node],))
            t.start()
            initMsg = self.createNewMessage("NEIGHBOR_INIT", self.localNodeId)
            self.conn[node].send(initMsg)
        except:
            pass

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
        if self.localNodeId in self.freeNodes:
            self.freeNodes.remove(self.localNodeId)
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
            aliveTimer = threading.Timer(int(self.config['alivetimeout']),handleTimeout, args=(self, msg.src,))
            aliveTimer.start()
            self.neighbors[msg.src] = (aliveTimer, 0)

        elif msg.type == "UPDATE":
            if len(msg.data) > 0:
                freeList = msg.data.split(",")
                for node in freeList:
                    if len(node) > 0 and len(node) < 22 and node not in self.freeNodes:
                        self.freeNodes.append(node)

        elif msg.type == "RES_AVL":
            if msg.data not in self.freeNodes:
                self.freeNodes.append(msg.data)
            msg.ttl -= 1
            if msg.ttl != 0:
                newMsg = self.createNewMessage(msg.type, msg.data, msg.ttl)
                self.sendExceptSource(newMsg, msg.src)

        elif msg.type == "RES_UNAVL":
            if msg.data in self.freeNodes:
                self.freeNodes.remove(msg.data)
            if self.jobmgr.status == 'JOBEXEC':
                if msg.data in self.jobmgr.reservedNodes and self.jobmgr.reservedNodes[msg.data] >= 0:
                    self.jobmgr.unScheduledQueue.put(self.jobmgr.reservedNodes[msg.data])
                    del self.jobmgr.reservedNodes[msg.data]
            msg.ttl -= 1
            if msg.ttl != 0:
                newMsg = self.createNewMessage(msg.type, msg.data, msg.ttl)
                self.sendExceptSource(newMsg, msg.src)

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
            client.close()
            if self.jobmgr.curJob != None:
                self.jobmgr.curJob.isTerminated = True
                if self.jobmgr.curJob.process.is_running() == True:
                    self.jobmgr.curJob.process.kill()
            self.lock.release()
            return False

        elif msg.type == "JOB_CODE":
            self.lock.release()
            self.jobmgr.jobStatus.put('NEW_JOB_REQUEST')
            if self.getJob(client, msg) == False:
                self.jobmgr.status = 'AVAILABLE'
                return False
            self.jobmgr.runJob()
            return False

        elif msg.type == "JOB_COMPLETE":
            if self.jobmgr.curJob == None:
                self.lock.release()
                return False
            chunkindex = -1
            if msg.src in self.jobmgr.reservedNodes:
                chunkindex = self.jobmgr.reservedNodes[msg.src]
                
            self.lock.release()
            if chunkindex == -1:
                return False
            self.handleJobResponse(msg, chunkindex, client)
            return False

        elif msg.type == "CPU_REQUEST":
            respMsg = ""
            if self.jobmgr.status == 'AVAILABLE':
                maxSpeed = 0.0
                for info in cpu.info:
                    maxSpeed += float(info['cpu MHz'])
                curSpeed = maxSpeed * (100.0 - psutil.cpu_percent(interval=1))
                print 'Current Idle CPU Speed is: ' + str(curSpeed)
                respMsg = self.createNewMessage('ACK', str(curSpeed))
            else:
                respMsg = self.createNewMessage('NACK','')
            try:
                client.send(respMsg)
                client.close()
            except:
                pass
            self.lock.release()
            return False

        else:
            self.lock.release()
            return False

        self.lock.release()
        return True

    def createNewMessage(self, msgType, data, ttl=2):
        msg = self.localNodeId + "-" + str(self.seqno) + "-" + str(ttl) + "-" + msgType + "-" + data
        formattedMsg = "%04d" % len(msg) + "-" + msg
        self.seqno += 1
        return formattedMsg

    def sendExceptSource(self, msg, src):
        for key in self.conn:
            if key == src:
                continue
            try:
                self.conn[key].send(msg)
            except:
                pass

    def reserveNode(self):
        freeList = []
        self.lock.acquire()
        print self.jobmgr.reservedNodes
        print self.freeNodes
        if len(self.freeNodes) < 1:
            self.lock.release()
            print "Reserve node failing due to less number of free nodes"
            return 'FAILURE'
        for node in self.freeNodes:
            if node not in self.jobmgr.reservedNodes:
                freeList.append(node)
            else:
                print node + " is in reserved nodes already!"
        self.lock.release()

        if len(freeList) < 1:
            print "Reserve node failing due to nodes in reserved list"
            return 'FAILURE'
    
        reqMsg = self.createNewMessage("RESERVE_REQ", self.localNodeId)
        for node in freeList:
            try:
                print "Sending RESERVE_REQ to node: " + node
                sock = createConn(node)
                sock.settimeout(5.0)
                sock.send(reqMsg)
                if self.waitForMsg(sock,'ACK') == True:
                    self.lock.acquire()
                    self.jobmgr.reservedNodes[node] = -1
                    self.lock.release()
                    sock.close()
                    return node
                else:
                    sock.close()
                    print "RESERVE_REQ failed due to " + msg.type
            except Exception,e:
                print "Exception:%s" % e
        return 'FAILURE'

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
            data = sock.recv((size - offset))
            if len(data) == 0:
                break
            fileObj.write(data)
            offset += len(data)
            if offset >= size:
                break
        fileObj.close()

    def waitForMsg(self, sock, msgType):
        try:
            sock.settimeout(3.0)
            data = recvMessage(sock)
            reply = Message(data)
            sock.settimeout(None)
            if reply.type != msgType:
                return False
            else:
                return True
        except:
            sock.settimeout(None)
            return False

    def scheduleJob(self, job, chunkindex, node, unScheduledQueue):
        try:
            sock = createConn(node)
            codeSize = os.stat(job.srcFile).st_size
            codeMsg = self.createNewMessage("JOB_CODE", str(codeSize))
            sock.send(codeMsg)
            if self.waitForMsg(sock,'ACK') == False:
                unScheduledQueue.put(chunkindex)
                return
            
            self.sendFile(sock, job.srcFile)
            if self.waitForMsg(sock,'ACK') == False:
                unScheduledQueue.put(chunkindex)
                return

            chunkFile = os.path.join(self.jobmgr.jobDir, 'chunk' + str(chunkindex))
            dataSize = os.stat(chunkFile).st_size
            dataMsg = self.createNewMessage("JOB_DATA", str(dataSize))
            sock.send(dataMsg)
            if self.waitForMsg(sock,'ACK') == False:
                unScheduledQueue.put(chunkindex)
                return
            
            self.sendFile(sock, chunkFile)
            if self.waitForMsg(sock,'ACK') == False:
                unScheduledQueue.put(chunkindex)
                return

            timeoutMsg = self.createNewMessage("JOB_TIMEOUT", str(job.timeout))
            sock.send(timeoutMsg)
            if self.waitForMsg(sock,'ACK') == False:
                unScheduledQueue.put(chunkindex)
                return

            self.lock.acquire()
            self.jobmgr.reservedNodes[node] = chunkindex
            self.lock.release()
            sock.close()

        except Exception, e:
            print "Exception in Job Schedule:%s" % e
            traceback.print_exc()
            unScheduledQueue.put(chunkindex)
            sock.close()
            return

    def getJob(self, sock, msg):
        try:
            ackMsg = self.createNewMessage("ACK", "")
            sock.send(ackMsg)
            self.jobmgr.jobStatus.put('WAIT_FOR_CODE')
            codeSize = int(msg.data)
            codeFile = os.path.join(self.jobmgr.jobDir, "script.py")
            dataFile = os.path.join(self.jobmgr.jobDir, "data.txt")
            opFile = os.path.join(self.jobmgr.jobDir, "op.txt")
            print codeFile
            self.recvFile(sock, codeFile, codeSize)
            os.chmod(codeFile, 0777)
            sock.send(ackMsg)
            self.jobmgr.jobStatus.put('WAIT_FOR_DATA')
            # To allow timeouts for JOB_DATA msg
            sock.settimeout(3.0)
            data = recvMessage(sock)
            msg = Message(data)
            if msg.type != "JOB_DATA":
                return False
            sock.settimeout(None)
            sock.send(ackMsg)
            dataSize = int(msg.data)
            self.recvFile(sock, dataFile, dataSize)
            sock.send(ackMsg)
            self.jobmgr.jobStatus.put('WAIT_FOR_TIMEOUT')
            sock.settimeout(3.0)
            data = recvMessage(sock)
            msg = Message(data)
            # To allow timeouts for JOB_TIMEOUT msg
            if msg.type != "JOB_TIMEOUT":
                return False
            sock.settimeout(None)
            sock.send(ackMsg)
            job = Job(dataFile, codeFile, opFile, 0, False, False, int(msg.data))
            job.owner = msg.src
            self.jobmgr.curJob = job
            sock.close()

        except Exception, e:
            print "Exception in getJob: %s" % e
            self.jobmgr.jobStatus.put('JOB_RECEIVED_FAILED')
            traceback.print_exc()
            sock.close()
            return False
        return True

    def sendResponse(self, job):
        try:
            sock = createConn(job.owner)
            opsize = os.stat(job.opFile).st_size
            opMsg = self.createNewMessage("JOB_COMPLETE", str(opsize) + ":" + str(job.cost))
            sock.send(opMsg)
            if self.waitForMsg(sock,'ACK') == False:
                print "Incrementing account balance by: " + str(job.timeout)
                self.jobmgr.accountBalance += job.timeout
                self.jobmgr.jobStatus.put('RESPONSE_FAILED:' + str(job.timeout))
                return
            self.jobmgr.jobStatus.put('SENDING_RESULTS')
            self.sendFile(sock, job.opFile)
            self.waitForMsg(sock,'ACK')
            sock.close()
            print "Incrementing account balance by: " + str(job.cost)
            self.jobmgr.accountBalance += job.cost
            self.jobmgr.jobStatus.put('JOB_COMPLETED:' + str(job.cost))
            return
        except Exception, e:
            print "Exception in sendResponse: %s" % e
            print "Incrementing account balance by: " + str(job.cost)
            self.jobmgr.accountBalance += job.timeout
            self.jobmgr.jobStatus.put('RESPONSE_FAILED:' + str(job.cost))
            traceback.print_exc()
            sock.close()
            return
            
    def handleJobResponse(self, msg, chunkindex, sock):
        try:
            data = msg.data.split(":")
            opsize = int(data[0])
            ackMsg = self.createNewMessage("ACK", "")
            sock.send(ackMsg)
            resultFile = os.path.join(self.jobmgr.jobDir, 'result' + str(chunkindex) + '.txt')
            self.recvFile(sock, resultFile, opsize)
            sock.send(ackMsg)
            sock.close()
            self.jobmgr.chunkStatus.put(chunkindex)
            self.jobmgr.curJob.cost -= int(data[1])
            print "Decrementing account balance by: " + data[1]
        except:
            print "Failure during getting job response! Rescheduling Chunk " + str(chunkindex)
            self.jobmgr.unScheduledQueue.put(chunkindex)
    
    def releaseNodes(self):
        self.lock.acquire()
        relMsg = self.createNewMessage("RELEASE_REQ","")
        for node in self.jobmgr.reservedNodes:
            if self.jobmgr.reservedNodes[node] >= 0:
                try:
                    sock = createConn(node)
                    sock.send(relMsg)
                    sock.close()
                except:
                    pass
        self.jobmgr.reservedNodes = {}
        self.lock.release()
    
    def getCPUInfo(self, numNodes):
        self.lock.acquire()
        freeList = self.freeNodes[:]
        print freeList
        self.lock.release()
        curCPU = {}
        count = 0
        cpureqMsg = self.createNewMessage('CPU_REQUEST','')
        for node in freeList:
            try:
                sock = createConn(node)
                sock.send(cpureqMsg)
                sock.settimeout(3.0)
                data = recvMessage(sock)
                msg = Message(data)
                sock.close()
                if msg.type == 'ACK':
                    curCPU[node] = float(msg.data)
                    count += 1
                    if count == (numNodes * 2):
                        break
            except Exception, e:
                traceback.print_exc()
                pass
        print curCPU
        sortedList = sorted(curCPU, key=curCPU.get, reverse=True)
        self.lock.acquire()
        self.freeNodes = sortedList[:]
        for node in freeList:
            if node not in curCPU:
                self.freeNodes.append(node)
        print self.freeNodes
        self.lock.release()
            
                
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
    try:
        data = requests.get("http://" + server + "/register/" + str(localIP) + "/" + str(localPort))
        neighbor_list = json.loads(data.text)
        return neighbor_list
    except:
        return "SERVER_FAILURE"

def remove_node(localIP, localPort, nodeIP, nodePort, server):
    try:
        data = requests.get("http://" + server + "/unregister/" + str(localIP) + "/" + str(localPort) + "/" + str(nodeIP) + "/" + str(nodePort))
        return json.loads(data.text)
    except:
        return "SERVER_FAILURE"

def disconnect_node(localIP, localPort, server):
    try:
        data = requests.get("http://" + server + "/disconnect/" + str(localIP) + "/" + str(localPort))
        return json.loads(data.text)
    except:
        return "SERVER_FAILURE"

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
