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
import resource
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
        self.jobStatus = Queue.Queue(maxsize=0)
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
        self.jobStatus.put('NEW_JOB_REQUEST')
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
        self.jobStatus.put('STARTED_EXECUTION')
        t = threading.Thread(target=executeJob, args=(self,))
        t.start()
        return

    def completeJob(self):
        if self.status == 'DISCONNECTED':
            self.jobStatus.put('NODE_FAILURE')
            self.curJob = None
            return
        if self.curJob.isTerminated == False:
            self.jobStatus.put('FINISHED_EXECUTION')
            self.nwmgr.sendResponse(self.curJob)
        else:
            self.jobStatus.put('EXECUTION_TERMINATED')
            
        self.status = 'AVAILABLE'
        print 'Made node available!'
        self.curJob = None
        
def scheduleJob(jobmgr, job):
    jobmgr.jobStatus.put('SPLITTING_JOB')
    jobmgr.nwmgr.getCPUInfo(job.numNodes)
    splitJob(jobmgr, job)
    jobmgr.jobStatus.put('SCHEDULING_JOB')
    jobmgr.jobTimer = threading.Timer(1, handleJobTimeout, args=(jobmgr,))
    jobmgr.jobTimer.start()

    while True:
        chunkindex = jobmgr.unScheduledQueue.get()
        print "Scheduling chunk index " + str(chunkindex)
        if chunkindex == -1:
            print "Job Completed"
            jobmgr.jobStatus.put('MERGING_RESULTS')
            mergeResults(jobmgr, job)
            jobmgr.curJob = None
            return
        node = jobmgr.nwmgr.reserveNode()
        if node == 'FAILURE':
            print "Job Execution Failed"
            jobmgr.jobStatus.put('FAILED_EXECUTION')
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
        try:
            os.remove(resultFile)
        except:
            pass
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

def setProcessLimits():
    # Read the config file
    config = ConfigParser.ConfigParser()
    config.read('config.cfg')
    sandboxingConfig = ConfigSectionMap(config, "SandboxingParams")

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (int(sandboxingConfig['nfile']), hard))
    soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
    resource.setrlimit(resource.RLIMIT_NPROC, (int(sandboxingConfig['nproc']), hard))
    soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
    resource.setrlimit(resource.RLIMIT_STACK, (int(sandboxingConfig['stacksize']), hard))

def executeJob(jobmgr):
    try:
        job = jobmgr.curJob
        ipObj = open(job.ipFile, 'r')
        opObj = open(job.opFile, 'w')
        startTime = time.time()
        job.process = psutil.Popen([sys.executable, job.srcFile], preexec_fn=setProcessLimits,
                             stdin=ipObj, stdout=opObj, stderr=opObj)
        job.process.wait(timeout=job.timeout)
        job.cost = int(math.ceil(float(time.time() - startTime)))
    except Exception, e:
        if job.process.is_running() == True:
            job.process.kill()
        print "Exception in executeJob: %s" % e
        traceback.print_exc()
        jobmgr.jobStatus.put('FAILED_EXECUTION')
        job.cost = job.timeout
        opObj.write("Job Execution Caused Exception! \n")
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
        jobCost = (jobmgr.curJob.numNodes * jobmgr.curJob.timeout) - jobmgr.curJob.cost
        jobmgr.jobStatus.put('JOB_COMPLETED:' + str(jobCost))
        print "Final account balance is: " + str(jobmgr.accountBalance)
        print "Added chunkindex -1 to unsched Queue"
    else:
        jobmgr.jobTimer = threading.Timer(1, handleJobTimeout, args=(jobmgr,))
        jobmgr.jobTimer.start()
    return
