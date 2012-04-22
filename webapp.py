#!/usr/bin/env python
from flask import Flask,flash, request,render_template, Response,session,g
import json
import StringIO, json, hashlib, random, os , base64, time, math, sqlite3, sys
import urllib, urllib2, datetime
from jobmgr import *
import socket
from job import *

app = Flask(__name__)
mgr = None
appMode = None

@app.route('/', methods=['GET'])
def index():
	global appMode
	if appMode == None:
		appMode = 'Disconnected'
	return render_template('index.html', mode=appMode, error="")

@app.route('/home', methods=['GET'])
def home():
	action = request.args.get('fn','')
	if  action == 'connect':
		return connect()
	elif action == 'disconnect':
		return disconnect()
	elif action == 'provider':
		return provider()
	elif action == 'consumer':
		return consumer()
	else:
		global appMode
		return render_template('index.html', mode=appMode, error="")

def connect():
	global appMode
	port = get_open_port()
	config = ConfigParser.ConfigParser()
	config.read('config.cfg')
	nwMgrConfig = ConfigSectionMap(config, "NetworkManager")
	neighbor_list = register_node(getLocalIP(), port, nwMgrConfig['serverip'])
	if neighbor_list == 'SERVER_FAILURE':
		return render_template('index.html', mode=appMode, error="Server Internal Error!")
	global mgr
	mgr = jobManager(port, neighbor_list)
	appMode = 'Connected'
	return render_template('index.html', mode=appMode, error="")

def disconnect():
	error = ""
	global appMode
	try:
		global mgr
		mgr.destroyManager()
		mgr = None
		appMode = 'Disconnected'
	except:
		error = "Server Internal Error!"
	return render_template('index.html', mode=appMode, error=error)

def provider():
	global mgr
	global appMode
	if mgr.curJob == None:
		mgr.makeAvailable()
		appMode = 'Provider'
		return render_template('index.html', mode=appMode, error="")
	else:
		error = "Your job is being run on remote nodes currently! Changing mode would lose data!"
		return render_template('index.html', mode=appMode, error=error)

def consumer():
	global mgr
	global appMode
	if mgr.curJob == None:
		mgr.makeUnavailable()
		appMode = 'Consumer'
		return render_template('index.html', mode=appMode, error="")
	else:
		error = "You are currently running a remote job! Changing mode would lose data!"
		return render_template('index.html', mode=appMode, error=error)

@app.route('/addjob', methods=['POST'])
def addjob():
	mergeResults = False
	if request.form['merge'] and request.form['merge'] == "True":
		mergeResults = True
	splitByLine = True
	if request.form['splitoption'] == "Bytes":
		splitByLine = False
	if os.path.isfile(request.form['ipfile']) == False:
		return render_template('home.html', status="unavailable")
	if os.path.isfile(request.form['srcfile']) == False:
		return render_template('home.html', status="unavailable")
	if os.path.exists(request.form['opfile']) == False:
		return render_template('home.html', status="unavailable")
	if int(request.form['numnodes']) <= 0:
		return render_template('home.html', status="unavailable")
	if int(request.form['timeout']) <= 0:
		return render_template('home.html', status="unavailable")
	global mgr
	job = Job(request.form['ipfile'], request.form['srcfile'], 
		  request.form['opfile'], int(request.form['numnodes']), 
		  mergeResults, splitByLine, int(request.form['timeout']))
	mgr.addJob(job)
	return render_template('home.html', status="unavailable")

def get_open_port():
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("",0))
	port = s.getsockname()[1]
        s.close()
        return port

if __name__== "__main__":
	app.debug = True
	app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'
	app.run('0.0.0.0', int(sys.argv[1]))

