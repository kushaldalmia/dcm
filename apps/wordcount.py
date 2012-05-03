import os, sys

if __name__ == "__main__":
    wordMap = {}
    for line in sys.stdin:
        words = line.rstrip('\n').rstrip(", ").rstrip(". ").split(' ')
        for index in range(0, len(words)):
            if words[index] in wordMap:
                count = wordMap[words[index]]
                wordMap[words[index]] = count + 1
            else:
                wordMap[words[index]] = 1

    for key in wordMap:
        print key + " = " + str(wordMap[key])
