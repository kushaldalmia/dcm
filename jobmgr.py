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
        #self.status = 'JOBEXEC'
        #self.splitJob(self.curJob)
        #for i in range(0, job.numNodes):
        #   self.nwmgr.scheduleJob(job.srcFile, "chunk" + str(i))
        #return True
        
    def splitJob(self, job):
        numLines = sum(1 for line in open(job.ipFile))
        lpf = int(math.ceil(float(numLines)/float(job.numNodes)))
        cmd = "split -a 1 -l " + str(lpf) + " -d " + job.ipFile + " chunk"
        os.system(cmd)
        

    
