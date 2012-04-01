#!/usr/bin/env python
from flask import Flask,flash, request,render_template, Response,session,g
import json
import StringIO, json, hashlib, random, os , base64, time, math, sqlite3, sys
import urllib, urllib2, datetime
from nwmgr import *

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
	mgr = nwManager(port, neighbor_list, nwMgrConfig)
	mgr.startManager()
	return render_template('home.html')

@app.route('/disconnect', methods=['GET'])
def disconnect():
	# Cleanly close mgr
	return render_template('index.html')

if __name__== "__main__":
	app.debug = True
	app.run('0.0.0.0', 4444)
