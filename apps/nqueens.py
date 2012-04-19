from math import *
import sys

chosen = {}
n = 12

def place(xpos, ypos):
    if (ypos in chosen.values()):
        return False
    opponent = 1
    while(opponent < xpos):
        if abs(chosen[opponent]-ypos) == abs(opponent-xpos):
            return False
        opponent+=1
    return True

def clear_all_future_positions(xpos):
    for i in range(xpos,n+1):
       chosen[i]=None

def NQueens(xpos, end):
 # print 'NQueens(',xpos,') entering'
    for ypos in range(1, n + 1):
        clear_all_future_positions(xpos)
        if place(xpos, ypos):
            chosen[xpos] = ypos
   # print 'chosen=',chosen
            if (xpos==end):
                for opponent in chosen:
                    print chosen[opponent]
                print '------------------'
            else:
                NQueens(xpos+1, end)
 # print 'NQueens(',xpos,') returns'

def main():
    for line in sys.stdin:
        seed = line.split(',')
        chosen[int(seed[0])] = int(seed[1])
        NQueens(2, n)

if __name__=="__main__":
    main()
