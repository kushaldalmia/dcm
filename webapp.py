#!/usr/bin/env python
from flask import Flask,flash, request,render_template, Response,session,g
import json
import StringIO, json, hashlib, random, os , base64, time, math, sqlite3, sys
import urllib, urllib2, datetime
from jobmgr import *
from job import *

app = Flask(__name__)
mgr = None

@app.route('/', methods=['GET'])
def index():
	return render_template('index.html')

@app.route('/connect', methods=['GET'])
def connect():
	port = int(request.args.get('port',''))
	config = ConfigParser.ConfigParser()
	config.read('config.cfg')
	nwMgrConfig = ConfigSectionMap(config, "NetworkManager")
	neighbor_list = register_node(getLocalIP(), port, nwMgrConfig['serverip'])
	if neighbor_list == 'ALREADY_CONNECTED':
		return render_template('home.html', status="unavailable")
	if neighbor_list == 'SERVER_FAILURE':
		return render_template('index.html')
	global mgr
	mgr = jobManager(port, neighbor_list)
	return render_template('home.html', status="unavailable")

@app.route('/disconnect', methods=['GET'])
def disconnect():
	global mgr
	mgr.destroyManager()
	mgr = None
	return render_template('index.html')

@app.route('/available', methods=['GET'])
def available():
	global mgr
	mgr.makeAvailable()
	return render_template('home.html', status="available")

@app.route('/unavailable', methods=['GET'])
def unavailable():
	global mgr
	mgr.makeUnavailable()
	return render_template('home.html', status="unavailable")

@app.route('/addjob', methods=['POST'])
def addjob():
	mergeResults = False
	if request.form['merge'] == "True":
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

if __name__== "__main__":
	app.debug = True
	app.run('0.0.0.0', int(sys.argv[1]))

