import json
import requests
import sys
import os
import math
import time
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
        if self.nwmgr.reserveNodes(job.numNodes) == False:
            print "Unable to reserve nodes for Job!"
            return False
        print "Job Manager reserved nodes for Job!"
        self.curJob = job
        self.status = 'JOBSCHED'
        t = threading.Thread(target=scheduleJob, args=(self, self.curJob,))
        t.start()
        return True

def scheduleJob(jobmgr, job):
    splitJob(job)
    schedThreads = []
    threadStatus = []
    for i in range(0, job.numNodes):
        schedThreads[i] = threading.Thread(target=jobmgr.nwmgr.scheduleJob, args=(job.srcFile, "chunk" + str(i), i, threadStatus,))
        schedThreads[i].start()
    for t in schedThreads:
        t.join()
    for i in range(0, job.numNodes):
        if threadStatus[i] == -1:
            # reschedule chunk i
            pass
    return

def splitJob(job):
    numLines = sum(1 for line in open(job.ipFile))
    lpf = int(math.ceil(float(numLines)/float(job.numNodes)))
    cmd = "split -a 1 -l " + str(lpf) + " -d " + job.ipFile + " chunk"
    os.system(cmd)
