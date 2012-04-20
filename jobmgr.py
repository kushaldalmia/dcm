import json
import requests
import sys
import shutil
import os
import math
import time
import Queue
import subprocess
import tempfile
from message import *
from socket import *
import SocketServer
import threading
import ConfigParser
from nwmgr import *

class jobManager:

    def __init__(self, localPort, neighborList):
        self.nwmgr = nwManager(localPort, neighborList, self)
        self.nwmgr.startManager()
        self.status = 'CONNECTED'
        self.curJob = None
        self.reservedBy = None
        self.reservedNodes = {}
        self.chunkStatus = Queue.Queue(maxsize=0)
        self.unScheduledQueue = Queue.Queue(maxsize=0)
        self.jobDir = tempfile.mkdtemp()
        self.accountBalance = 0
    
    def makeAvailable(self):
        self.status = 'AVAILABLE'
        self.nwmgr.makeAvailable()
        
    def makeUnavailable(self):
        self.status = 'UNAVAILABLE'
        self.nwmgr.makeUnavailable()

    def destroyManager(self):
        self.status = 'DISCONNECTED'
        self.nwmgr.destroyManager()

    def addJob(self, job):
        if self.curJob != None or self.status == 'AVAILABLE':
            return False
        print "Job started at : " + str(time.time())
        self.unScheduledQueue = Queue.Queue(maxsize=0)
        self.chunkStatus = Queue.Queue(maxsize=0)
        self.reservedNodes = {}
        for i in range(0, job.numNodes):
            self.unScheduledQueue.put(i)
        self.curJob = job
        self.accountBalance -= (job.numNodes * job.timeout)
        print "Addjob: Current balance: " + str(self.accountBalance)
        t = threading.Thread(target=scheduleJob, args=(self, self.curJob,))
        t.start()
        self.status = 'JOBEXEC'
        return True
    
    def runJob(self):
        t = threading.Thread(target=executeJob, args=(self,))
        t.start()
        return

    def completeJob(self):
        self.nwmgr.sendResponse(self.curJob)
        self.status = 'AVAILABLE'
        print 'Made node available!'
        self.curJob = None
        
def scheduleJob(jobmgr, job):
    
    jobmgr.nwmgr.getCPUInfo(job.numNodes)
    splitJob(jobmgr, job)
    jobmgr.jobTimer = threading.Timer(1, handleJobTimeout, args=(jobmgr,))
    jobmgr.jobTimer.start()

    while True:
        chunkindex = jobmgr.unScheduledQueue.get()
        print "Scheduling chunk index " + str(chunkindex)
        if chunkindex == -1:
            print "Job Completed"
            mergeResults(jobmgr, job)
            jobmgr.curJob = None
            return
        node = jobmgr.nwmgr.reserveNode()
        if node == 'FAILURE':
            print "Job Execution Failed"
            jobmgr.nwmgr.releaseNodes()
            jobmgr.accountBalance += (job.numNodes * job.timeout)
            jobmgr.curJob = None
            return
        t = threading.Thread(target=jobmgr.nwmgr.scheduleJob, args=(job, chunkindex, node, jobmgr.unScheduledQueue,))
        t.start()
    
    return

def mergeResults(jobmgr, job):
    if job.mergeResults == True:
        # merge all the files into one result file
        resultFile = os.path.join(job.opFile, 'result.txt')
        for index in range(0, job.numNodes):
            chunkResultFile = os.path.join(jobmgr.jobDir, 'result' + str(index) + '.txt')
            cmd = 'cat ' + chunkResultFile + ' >> ' + resultFile
            os.system(cmd)
    else:
        # move all the files to output folder
        for index in range(0, job.numNodes):
            srcFile = os.path.join(jobmgr.jobDir, 'result' + str(index) + '.txt')
            dstFile = os.path.join(job.opFile, 'result' + str(index) + '.txt')
            shutil.move(srcFile, dstFile)

def splitJob(jobmgr, job):
    
    if job.splitByLine == True:
        numLines = sum(1 for line in open(job.ipFile))
        lpf = int(math.ceil(float(numLines)/float(job.numNodes)))
        cmd = "split -a 1 -l " + str(lpf) + " -d " + job.ipFile + " chunk"
    else:
        filesize = os.stat(job.ipFile).st_size
        bpf = int(math.ceil(float(filesize)/float(job.numNodes)))
        cmd = "split -a 1 -b " + str(bpf) + " -d " + job.ipFile + " chunk"
    os.system(cmd)

    # move chunk files to temp folder
    for index in range(0, job.numNodes):
        shutil.move('chunk' + str(index), os.path.join(jobmgr.jobDir, 'chunk' + str(index)))

def executeJob(jobmgr):
    try:
        job = jobmgr.curJob
        ipObj = open(job.ipFile, 'r')
        opObj = open(job.opFile, 'w')
        startTime = time.time()
        p = subprocess.Popen([sys.executable, job.srcFile], stdin=ipObj, stdout=opObj, stderr=opObj)
        p.wait()
        job.cost = int(math.ceil(float(time.time() - startTime)))
    except Exception, e:
        print "Exception in executeJob: %s" % e
        traceback.print_exc()
        job.cost = job.timeout
        opObj.write("Job Execution Caused Exception!")
    ipObj.close()
    opObj.close()
    jobmgr.completeJob()
    
def handleJobTimeout(jobmgr):
    if jobmgr.curJob == None:
        return
    
    if jobmgr.chunkStatus.qsize() == jobmgr.curJob.numNodes:
        jobmgr.unScheduledQueue.put(-1)
        jobmgr.chunkStatus = Queue.Queue(maxsize=0)
        jobmgr.accountBalance += jobmgr.curJob.cost
        print "Final account balance is: " + str(jobmgr.accountBalance)
        print "Added chunkindex -1 to unsched Queue"
    else:
        jobmgr.jobTimer = threading.Timer(1, handleJobTimeout, args=(jobmgr,))
        jobmgr.jobTimer.start()
    return
