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
	serverAddr = nwMgrConfig['serverip'] + ':' + nwMgrConfig['serverport']
	neighbor_list = register_node(getLocalIP(), port, serverAddr)
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

@app.route('/addjob', methods=['GET'])
def addjob():
	global mgr
	job = Job("", "", "", 2)
	mgr.addJob(job)
	return render_template('home.html', status="unavailable")

if __name__== "__main__":
	app.debug = True
	app.run('0.0.0.0', int(sys.argv[1]))

