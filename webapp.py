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
statusInfo = None
jobCost = ''
runningJob = False
providerHistory = []
consumerHistory = []

@app.route('/', methods=['GET'])
def index():
	global appMode
	if appMode == None:
		appMode = 'Disconnected'
	return render_template('index.html', mode=appMode, error="")

@app.route('/home', methods=['GET'])
def home():
	action = request.args.get('fn','')
	force = request.args.get('force','')
	if  action == 'connect':
		return connect()
	elif action == 'disconnect':
		return disconnect(force)
	elif action == 'provider':
		return provider()
	elif action == 'consumer':
		return consumer()
	else:
		global appMode
		error = ""
		if appMode == None:
			error = "Please connect to the DCM Network!"
		return render_template('index.html', mode=appMode, error=error)

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
	global statusInfo
	global jobCost
	global providerHistory
	global consumerHistory
	mgr = jobManager(port, neighbor_list)
	jobCost = ''
	statusInfo = []
	providerHistory = []
	consumerHistory = []
	t = threading.Thread(target=getJobStatus, args=(mgr.jobStatus, ))
	t.daemon = True
	t.start()
	appMode = 'Connected'
	return render_template('index.html', mode=appMode, error="")

def disconnect(force):
	error = ""
	global appMode
	global jobCost
	global statusInfo
	try:
		global mgr
		if mgr.curJob == None or len(force) > 0:
			mgr.destroyManager()
			mgr = None
			jobCost = ''
			statusInfo = []
			appMode = 'Disconnected'
		else:
			error = "You have active jobs running on your system! Are you sure you want to disconnect?"
	except:
		error = "Server Internal Error!"
	return render_template('index.html', mode=appMode, error=error)

def provider():
	global mgr
	global appMode
	global statusInfo
	global jobCost
	global runningJob
	if mgr.curJob == None:
		mgr.makeAvailable()
		appMode = 'Provider'
		statusInfo = []
		jobCost = ''
		runningJob = False
		return render_template('index.html', mode=appMode, error="")
	else:
		error = "Your job is being run on remote nodes currently! Changing mode would lose data!"
		return render_template('index.html', mode=appMode, error=error)

def consumer():
	global mgr
	global appMode
	global statusInfo
	global jobCost
	global runningJob
	if mgr.curJob == None:
		mgr.makeUnavailable()
		appMode = 'Consumer'
		statusInfo = []
		jobCost = ''
		runningJob = False
		return render_template('index.html', mode=appMode, error="")
	else:
		error = "You are currently running a remote job! Changing mode would lose data!"
		return render_template('index.html', mode=appMode, error=error)

@app.route('/runjob')
def runjob():
	global appMode
	global statusInfo
	global jobCost
	global runningJob
	if appMode == 'Connected' or appMode == 'Disconnected':
		error = "You need to be a Provider/Consumer to add/view jobs!"
		return render_template('runjob.html', mode=appMode, statusInfo=statusInfo, percentage='', jobCost=jobCost, error=error, runningJob=runningJob)
	if appMode == 'Provider':
		percentage = str(int(float(len(statusInfo)) * 12.5))
	elif appMode == 'Consumer':
		percentage = str(len(statusInfo) * 20)
	return render_template('runjob.html', mode=appMode, statusInfo=statusInfo, percentage=percentage, jobCost=jobCost, runningJob=runningJob)

@app.route('/addjob', methods=['POST'])
def addjob():
	global appMode
	global mgr
	global statusInfo
	global jobCost
	global runningJob
	error = ""
	if appMode != 'Consumer':
		error = "You need to be in Consumer mode to run jobs!"
		return render_template('runjob.html', mode=appMode, statusInfo=statusInfo, percentage='', jobCost=jobCost, error=error, runningJob=runningJob)
	if mgr.curJob != None:
		error = "You are currently running a job on DCM! Please wait for it to finish!"
		return render_template('runjob.html', mode=appMode, statusInfo=statusInfo, percentage='', jobCost=jobCost, error=error, runningJob=runningJob)

	mergeResults = False
	if request.form['merge'] and request.form['merge'] == "True":
		mergeResults = True
	splitByLine = True
	if request.form['splitoption'] == "Bytes":
		splitByLine = False
	if os.path.isfile(request.form['ipfile']) == False:
		error = "Input File Does Not Exist!"
		return render_template('runjob.html', mode=appMode, error=error)
	if os.path.isfile(request.form['srcfile']) == False:
		error = "Source File Does Not Exist!"
		return render_template('runjob.html', mode=appMode, error=error)
	if os.path.exists(request.form['opfile']) == False:
		error = "Output Directory Does Not Exist!"
		return render_template('runjob.html', mode=appMode, error=error)
	if int(request.form['numnodes']) <= 0:
		error = "Number of nodes should be a positive number!"
		return render_template('runjob.html', mode=appMode, error=error)
	if int(request.form['timeout']) <= 0:
		error = "Timeout should be a positive value (in secs)!"
		return render_template('runjob.html', mode=appMode, error=error)
	job = Job(request.form['ipfile'], request.form['srcfile'], 
		  request.form['opfile'], int(request.form['numnodes']), 
		  mergeResults, splitByLine, int(request.form['timeout']))
	mgr.addJob(job)
	runningJob = True
	if error == "":
		return render_template('runjob.html', mode=appMode, statusInfo=statusInfo, percentage='', jobCost=jobCost, error=error, runningJob=runningJob)
	else:
		return redirect(url_for('/runjob'))

@app.route('/viewjob')
def viewjob():
	global appMode
	global providerHistory
	global consumerHistory
	global mgr

	if appMode == 'Connected' or appMode == 'Disconnected':
		error = "You need to be a Provider/Consumer to add/view jobs!"
		return render_template('viewjob.html', mode=appMode, error=error)
	else:
		return render_template('viewjob.html', mode=appMode, providerHistory=providerHistory, consumerHistory=consumerHistory, accBalance=mgr.accountBalance)

def get_open_port():
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("",0))
	port = s.getsockname()[1]
        s.close()
        return port

def getJobStatus(statusQueue):
	global statusInfo
	global jobCost
	global runningJob
	global providerHistory
	global consumerHistory
	global appMode

	while True:
		status = statusQueue.get()
		if status == 'NEW_JOB_REQUEST':
			statusInfo = []
			jobCost = ''
		elif ':' in status:
			info = status.split(":")
			status = info[0]
			jobCost = info[1]
			if appMode == 'Provider':
				providerHistory.append(int(jobCost))
			elif appMode == 'Consumer':
				consumerHistory.append(int(jobCost))
		if 'JOB_COMPLETED' in status or 'FAILED_EXECUTION' in status:
			runningJob = False
		print "Added " + status + " to statusInfo"
		statusInfo.append(status)

if __name__== "__main__":
	app.debug = True
	app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'
	app.run('0.0.0.0', int(sys.argv[1]))

