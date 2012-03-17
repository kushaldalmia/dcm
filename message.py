import os
import sys

class Message:

    def __init__(self, msgStr):
        msgFields = msgStr.split(":")
        self.sender = int(msgFields[0])
        self.seqno = int(msgFields[1])
        self.ttl = int(msgFields[2])
        self.type = msgFields[3]
        self.data = msgFields[4]

    def toString(self):
        return str(self.sender) + ":" + str(self.seqno) + ":" + str(self.ttl) + ":" + self.type + ":" + self.data
    
    
