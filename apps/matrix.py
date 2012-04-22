import random
import os
import pickle
import sys
from time import *
import cProfile
from boto.s3.connection import S3Connection
from boto.s3.key import Key

AWS_ACCESS_KEY_ID = 'AKIAIFAZ6DJSLGHN2EBA'
AWS_SECRET_ACCESS_KEY = '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'
BUCKET_NAME = AWS_ACCESS_KEY_ID.lower() + '-dcm'

def zero(m,n):
    # Create zero matrix
    new_matrix = [[0 for row in range(n)] for col in range(m)]
    return new_matrix
 
def rand(m,n):
    # Create random matrix
    new_matrix = [[random.random() for row in range(n)] for col in range(m)]
    return new_matrix
 
def write(matrix, filename):
    fileobj = open(filename, 'w')
    pickle.dump(matrix, fileobj)
    fileobj.close()

def show(matrix):
    # Print out matrix
    for col in matrix:
        print col 

def read(filename):
    conn = S3Connection(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    bucket = conn.get_bucket(BUCKET_NAME)
    key = bucket.get_key(filename)
    fileobj = open(filename, 'w')
    key.get_file(fileobj)
    fileobj.close()
    fileobj = open(filename, 'r')
    matrix = pickle.load(fileobj)
    return matrix
 
def mult(matrix1, matrix2, row):
    # Matrix multiplication
    if len(matrix1[0]) != len(matrix2):
        # Check matrix dimensions
        print 'Matrices must be m*n and n*p to multiply!'
    else:
        # Multiply if correct dimensions
        new_matrix = zero(1, len(matrix2[0]))
        for j in range(len(matrix2[0])):
            for k in range(len(matrix2)):
                new_matrix[0][j] += matrix1[row][k]*matrix2[k][j]
        return new_matrix
 
def time_mult(matrix1,matrix2):
    # Clock the time matrix multiplication takes
    start = clock()
    new_matrix = mult(matrix1,matrix2)
    end = clock()
    print 'Multiplication took ',end-start,' seconds'
 
def profile_mult(matrix1,matrix2):
    # A more detailed timing with process information
    # Arguments must be strings for this function
    # eg. profile_mult('a','b')
    cProfile.run('matrix.mult(' + matrix1 + ',' + matrix2 + ')')

if __name__ == "__main__":
    
    a = read("matrix_a.txt")
    b = read("matrix_b.txt")
  
    #print "A="
    #show(a)
    #print "B="
    #show(b)
    new_matrix = []
    for line in sys.stdin:
        limits = line.split(":")
        for line in range(int(limits[0]), int(limits[1])):
            row = int(line)
            new_matrix.append(mult(a, b, row))
   
    print new_matrix
    #write(new_matrix, "matrix_result.txt")
    #print "C="
    #show(new_matrix)
