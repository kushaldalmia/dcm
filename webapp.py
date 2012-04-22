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

@app.route('/', methods=['GET'])
def index():
	if 'mode' not in session:
		session['mode'] = 'Disconnected'
	return render_template('index.html', mode=session['mode'], error="")

@app.route('/connect', methods=['GET'])
def connect():
	port = get_open_port()
	config = ConfigParser.ConfigParser()
	config.read('config.cfg')
	nwMgrConfig = ConfigSectionMap(config, "NetworkManager")
	neighbor_list = register_node(getLocalIP(), port, nwMgrConfig['serverip'])
	if neighbor_list == 'SERVER_FAILURE':
		return render_template('index.html', mode=session['mode'], error="Server Internal Error!")
	global mgr
	mgr = jobManager(port, neighbor_list)
	session['mode'] = 'Connected'
	return render_template('index.html', mode=session['mode'], error="")

@app.route('/disconnect', methods=['GET'])
def disconnect():
	error = ""
	try:
		global mgr
		mgr.destroyManager()
		mgr = None
		session['mode'] = 'Disconnected'
	except:
		error = "Server Internal Error!"
	return render_template('index.html', mode=session['mode'], error=error)

@app.route('/provider', methods=['GET'])
def provider():
	global mgr
	mgr.makeAvailable()
	return render_template('home.html', status="available")

@app.route('/consumer', methods=['GET'])
def consumer():
	global mgr
	mgr.makeUnavailable()
	return render_template('home.html', status="unavailable")

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

