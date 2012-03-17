#!/usr/bin/env python
from flask import Flask,flash, request,render_template, Response,session,g
from flask import Flask, request, session, g, redirect, url_for, \
                  abort, render_template, flash, Response, send_file
from PIL import Image
from contextlib import closing
import StringIO, json, hashlib, random, os , base64, time, math, sqlite3, sys
import urllib, urllib2, datetime

app = Flask(__name__)
app.config.from_object(__name__)

#configs
DEBUG = True
DATABASE = '/tmp/dcm.db'
USERNAME = 'admin'
PASSWORD = 'default'
SECRET_KEY = '\xf1\xb1R\xb5\x07lQri\x87\x03\xc2/\xe3h[\xea\xd8\xef\xcd'

##############################################
# Database startup code 
##############################################
##############################################################
# Database startup 
##############################################################

def connect_db():
	print "Trying to connect to the Database " + DATABASE
        return sqlite3.connect(DATABASE)

def init_db():
	print "Attempting to create the databse "
	print DATABASE
        with closing(connect_db()) as db:
                with app.open_resource('schema.sql') as f:
			print f
                        db.cursor().executescript(f.read())
                db.commit()
        print "Database created successfully!"

@app.before_request
def before_request():
        g.db = connect_db()
	print "Got the handle for G"
	print g.db

@app.teardown_request
def teardown_request(exception):
        g.db.close()

def query_db(query, args=(), one=False):
    cur = g.db.execute(query, args)
    rv = [dict((cur.description[idx][0], value)
               for idx, value in enumerate(row)) for row in cur.fetchall()]
    return (rv[0] if rv else None) if one else rv




@app.route("/")
def hello():
	return "Nice try, But this is a bootstrap server, Try an extension to the URL"
	
@app.route("/register/<ip_add>/<port_no>/", methods =['GET','POST'])
def register(ip_add=None, port_no=None):
	print "register !" 
	print 30 * "*"
	print "request received to register Ip" + ip_add + "and Port" + port_no
	return "SUCCESS!"
	


if __name__== "__main__":

        if len(sys.argv) > 1 and sys.argv[1].strip() == 'init_db': init_db()
        if len(sys.argv) > 1 and sys.argv[1].strip() == 'remake_db': pass#init_db()
	app.run()

