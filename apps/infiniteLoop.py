import os, sys

if __name__ == "__main__":
    linkList = {}
    for line in sys.stdin:
        data = line.split(' ')
        linkList[int(data[0])] = int(data[1])

    index = linkList.keys()[0]
    while True:
        index = linkList[index]
        if index == 0:
            break
    print "No circular loop"

