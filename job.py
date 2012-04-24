import os
import sys

class Job:

    def __init__(self, ipFile="", srcFile="", opFile="", numNodes=0, mergeResults=False, splitByLine=True, timeout=0):
        self.ipFile = ipFile
        self.srcFile = srcFile
        self.opFile = opFile
        self.numNodes = numNodes
        self.owner = None
        self.process = None
        self.isTerminated = False
        self.mergeResults = mergeResults
        self.splitByLine = splitByLine
        self.timeout = timeout
        self.cost = (numNodes * timeout)
