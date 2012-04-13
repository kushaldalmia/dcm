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
        self.reservedNodes = []
        self.chunkLock = threading.Lock()
        self.chunkStatus = {}
    
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
        print "Job started at : " + time.time()
        if self.nwmgr.reserveNodes(job.numNodes) == False:
            print "Unable to reserve nodes for Job!"
            return False
        print "Job Manager reserved nodes for Job!"
        self.curJob = job
        self.status = 'JOBSCHED'
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
        self.curJob = None
        self.status = 'AVAILABLE'

def scheduleJob(jobmgr, job):
    # If job scheduling fails, update jobmgr status
    splitJob(job)
    schedThreads = []
    threadStatus = Queue.Queue(maxsize=0)

    for i in range(0, job.numNodes):
        jobmgr.chunkStatus[i] = False
        jobmgr.reservedNodes[i]['state'] = i

    for i in range(0, job.numNodes):
        t = threading.Thread(target=jobmgr.nwmgr.scheduleJob, args=(job, i, i, threadStatus,))
        schedThreads.append(t)
        t.start()

    for t in schedThreads:
        t.join()

    workingNodes = 0
    while threadStatus.empty() == False:
        status = threadStatus.get_nowait().split(":")
        index = int(status[0])
        state = int(status[1])
        jobmgr.reservedNodes[index]['state'] = state
        if state >= 0: 
            workingNodes += 1
    if workingNodes < job.numNodes:
        # Call rescheduling function
        pass
    jobmgr.jobTimer = threading.Timer(1, handleJobTimeout, args=(jobmgr,))
    jobmgr.jobTimer.start()
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
        print "executing job"
        p = subprocess.Popen([sys.executable, job.srcFile], stdin=ipObj, stdout=opObj)
        p.wait()
        # Check returncode for p; Send error to owner
        ipObj.close()
        opObj.close()
        jobmgr.completeJob()
    except:
        # Send error to owner
        pass

def handleJobTimeout(jobmgr):
    jobStatus = True
    jobmgr.chunkLock.acquire()
    for key in jobmgr.chunkStatus:
        if jobmgr.chunkStatus[key] == False:
            jobStatus = False
            break
    jobmgr.chunkLock.release()
    if jobStatus == True:
        print "Job Execution complete at " + time.time()
        jobmgr.status = 'CONNECTED'
        jobmgr.curJob = None
        jobmgr.reservedNodes = []
    else:
        print "Job Execution incomplete! Resetting check timer"
        jobmgr.jobTimer = threading.Timer(1, handleJobTimeout, args=(jobmgr,))
        jobmgr.jobTimer.start()

    # In case of multiple timeouts:
    # Fail current job
    # Release reserved nodes
    return
