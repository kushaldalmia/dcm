import json
import requests
import sys
import os
import math
import time
import Queue
import subprocess
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
    splitJob(job)
    
    jobmgr.jobTimer = threading.Timer(1, handleJobTimeout, args=(jobmgr,))
    jobmgr.jobTimer.start()

    while True:
        chunkindex = jobmgr.unScheduledQueue.get()
        print "Scheduling chunk index " + str(chunkindex)
        if chunkindex == -1:
            print "Job Completed"
            jobmgr.curJob = None
            return
        node = jobmgr.nwmgr.reserveNode()
        if node == 'FAILURE':
            print "Job Execution Failed"
            jobmgr.nwmgr.releaseNodes()
            jobmgr.curJob = None
            return
        t = threading.Thread(target=jobmgr.nwmgr.scheduleJob, args=(job, chunkindex, node, jobmgr.unScheduledQueue,))
        t.start()
    
    return

def splitJob(job):
    numLines = sum(1 for line in open(job.ipFile))
    lpf = int(math.ceil(float(numLines)/float(job.numNodes)))
    cmd = "split -a 1 -l " + str(lpf) + " -d " + job.ipFile + " chunk"
    os.system(cmd)

def executeJob(jobmgr):
    try:
        job = jobmgr.curJob
        ipObj = open(job.ipFile, 'r')
        opObj = open(job.opFile, 'w')
        print "executing job starting at " + str(time.time())
        p = subprocess.Popen([sys.executable, job.srcFile], stdin=ipObj, stdout=opObj, stderr=opObj)
        p.wait()
        print "job execution finished at " + str(time.time())
    except:
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
        print "Added chunkindex -1 to unsched Queue"
    else:
        jobmgr.jobTimer = threading.Timer(1, handleJobTimeout, args=(jobmgr,))
        jobmgr.jobTimer.start()
    return
