#!/usr/bin/env python
from flask import Flask,flash, request,render_template, Response,session,g
from flask import Flask, request, session, g, redirect, url_for, \
                  abort, render_template, flash, Response, send_file
from contextlib import closing
import json
import StringIO, json, hashlib, random, os , base64, time, math, sqlite3, sys
import urllib, urllib2, datetime
from message import *
import ConfigParser
from sendfile import sendfile
from socket import *
import threading
import traceback
import requests
import shutil

app = Flask(__name__)
app.config.from_object(__name__)

backupServer = None

#configs
DEBUG = True
DATABASE = '/tmp/dcm.db'
USERNAME = 'admin'
PASSWORD = 'default'
SECRET_KEY = '\xf1\xb1R\xb5\x07lQri\x87\x03\xc2/\xe3h[\xea\xd8\xef\xcd'
MAX_PEERS = 3
MSG_LEN_FIELD = 5

def connect_db():
	print "Trying to connect to the Database " + DATABASE
        return sqlite3.connect(DATABASE)

def init_db():
	print "Attempting to create the Database " + DATABASE
        with closing(connect_db()) as db:
                with app.open_resource('schema.sql') as f:
			db.cursor().executescript(f.read())
                db.commit()
        print "Database created successfully!"

@app.before_request
def before_request():
        g.db = connect_db()

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
	
## Register the IP and Port for the server
@app.route("/register/<ip_add>/<port_no>/", methods =['GET','POST'])
def register(ip_add=None, port_no=None):
	print "Request received to register IP Address: " + ip_add + " Port:" + port_no
	node_id = ip_add.strip() + ":" + port_no.strip()
	if request.remote_addr != backupServer:
		try:
			requests.get("http://" + backupServer + "/register/" + ip_add + "/" + port_no + "/")
		except:
			traceback.print_exc()
		pass
	# See if the IP:PORT is already registered 
	id_list = query_db('select node_id from Nodes where node_id=?',[node_id])
	if id_list == []:
		try:
			nodes_entries = query_db('SELECT * FROM Nodes ORDER BY ref_count')
			peerList = []
			count = 0
			for node in nodes_entries:
				peerList.append(node['node_id'])
				g.db.execute('update Nodes set ref_count=? where node_id=?',
						[node['ref_count'] + 1, node['node_id']])
				g.db.commit()
				count += 1
				if count == MAX_PEERS:
					break
			g.db.execute('insert into Nodes (node_id, ref_count)\
					values (?,?)', 
					[node_id, count] )
			g.db.commit()
			print "Successfully Added node " + node_id + " to Database!"
			return json.dumps(peerList)
		except Exception, e:
			print "Failed to add node " + node_id + " to Database!"
			print "Exception: %s" % e
			return json.dumps("SERVER_FAILURE")
			
	else:
		# Now we know that this node was already registered 
		print "ERROR: Node " + node_id + " already existing in DB!"
		return json.dumps("ALREADY_CONNECTED")
	return json.dumps("SERVER_FAILURE")

@app.route("/disconnect/<ip_add>/<port_no>/")
def disconnect(ip_add=None, port_no=None):
	print "Request received to disconnect IP Address: " + ip_add + " Port:" + port_no
	node_id = ip_add.strip() + ":" + port_no.strip()
	if request.remote_addr != backupServer:
		try:
			requests.get("http://" + backupServer + "/disconnect/" + ip_add + "/" + port_no + "/")
		except:
			pass

	id_list = query_db('select node_id from Nodes where node_id=?',[node_id])
	if len(id_list) > 0:
		try:
			query_db('delete from Nodes where node_id=?',[node_id])
			g.db.commit()
		except Exception, e:
			print "Exception: %s" % e
			return json.dumps("SERVER_FAILURE")
			  
@app.route("/unregister/<remote_ip>/<remote_port>/<ip_add>/<port_no>/")
def unregister(remote_ip=None, remote_port=None, ip_add=None, port_no=None):
	failed_node_id = ip_add.strip() + ":" + port_no.strip()
	neighbor_node_id = remote_ip.strip() + ":" + remote_port.strip()

	if request.remote_addr != backupServer:
		try:
			requests.get("http://" + backupServer + "/unregister/" + remote_ip + "/" + remote_port + "/" + ip_add + "/" + port_no + "/")
		except:
			pass
			  
	updatedRefCount = -1
	id_list = query_db('select node_id from Nodes where node_id=?',[failed_node_id])
	if len(id_list) > 0:
		try:
			query_db('delete from Nodes where node_id=?',[failed_node_id])
			g.db.commit()
		except Exception, e:
			print "Exception: %s" % e
			return json.dumps("SERVER_FAILURE")
	try:
		neighbor_data = query_db('select * from Nodes where node_id=?', [neighbor_node_id]) 
		if neighbor_data == []:
			return json.dumps("SERVER_FAILURE")
		else:
			updatedRefCount = neighbor_data[0]['ref_count'] - 1
			g.db.execute('update Nodes set ref_count=? where node_id=?',[updatedRefCount, neighbor_node_id])
			g.db.commit()
	except Exception, e:
		print "Exception: %s" % e
		return json.dumps("SERVER_FAILURE")
	newNeighbor = ""
	if updatedRefCount != -1 and updatedRefCount < MAX_PEERS:
		try:
			nodes_entries = query_db('SELECT * FROM Nodes ORDER BY ref_count')
			newNeighbor = ""
			for node in nodes_entries:
				if node['node_id'] != neighbor_node_id:
					newNeighbor = node['node_id']
					break
			if newNeighbor == "":
				return json.dumps("")
			g.db.execute('update Nodes set ref_count=? where node_id=?',[updatedRefCount + 1, neighbor_node_id])
                        g.db.commit()
			g.db.execute('update Nodes set ref_count=? where node_id=?',[nodes_entries[0]['ref_count'] + 1, newNeighbor])
                        g.db.commit()
			print "Successfully returned new neighbor " + newNeighbor + " for node: " + neighbor_node_id
		except:
			return json.dumps("SERVER_FAILURE")
	return json.dumps(newNeighbor)

def initBootstrap():
	config = ConfigParser.ConfigParser()
        config.read('../config.cfg')
        bootstrapConfig = ConfigSectionMap(config, "Bootstrap")
	localIP = getLocalIP()
	global backupServer
	if bootstrapConfig['server1'] == localIP:
		backupServer = bootstrapConfig['server2']
	else:
		backupServer = bootstrapConfig['server1']
	print "Backup Server is: " + backupServer
	backupAvailable = True
	port = int(bootstrapConfig['port'])
	try:
		requests.get("http://" + backupServer + "/")
	except Exception, e:
		traceback.print_exc()
		backupAvailable = False
	if backupAvailable == False:
		print "Backup Not Available! Initializing DB"
		init_db()
	else:
		print "Backup Available! Pulling from Primary!"
		getLatestDatabase(backupServer, port)
		connect_db()
	t = threading.Thread(target=connHandler, args=(port,))
	t.daemon = True
	t.start()
	return
	
def connHandler(port):
	# Initalize listening socket                                                                                                                                   
        server = socket(AF_INET, SOCK_STREAM)
        server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
	server.bind(('', port))
        server.listen(5)
        
	while True:
		try:
			client, addr = server.accept()
			t = threading.Thread(target=backupHandler, args=(client,))
			t.daemon = True
			t.start()
		except:
			print "Exception in connHandler"
			traceback.print_exc()
			server.close()
			return
	server.close()

def backupHandler(client):
	try:
		msg = Message(recvMessage(client))
		if msg.type == "GET_DB":
			print "Received GET_DB from backup!"
			shutil.copyfile(DATABASE, "\tmp\dcm-copy.db")
			fsize = os.stat('\tmp\dcm-copy.db').st_size
			msg = '0-0-0-' + 'ACK' + '-' + str(fsize)
			client.send("%04d" % len(msg) + "-" + msg)
			sendFile(client, '\tmp\dcm-copy.db')
			client.close()
	except Exception, e:
		print "Exception in backupHandler()"
		return
	return

def sendFile(sock, filename):
        srcfile = open(filename, "rb")
        offset = 0
        while True:
            sent = sendfile(sock.fileno(), srcfile.fileno(), offset, 65536)
            if sent == 0:
                break
	        offset += sent
        srcfile.close()


def recvMessage(sock):
    msgLen = sock.recv(MSG_LEN_FIELD)
    if len(msgLen) == 0:
        return ''
    msgLen = int(msgLen[:4])
    data = sock.recv(msgLen)
    return data


def getLatestDatabase(backup, port):
	try:
		sock = socket(AF_INET, SOCK_STREAM)
		sock.connect((backup, port))
		msg = '0-0-0-' + 'GET_DB' + '-'
		sock.send("%04d" % len(msg) + "-" + msg)
		data = recvMessage(sock)
		reply = Message(data)
		if reply.type == 'ACK':
			size = int(reply.data)
		else:
			sock.close()
			return False
		recvFile(sock, DATABASE, size)
		sock.close()
	except:
		traceback.print_exc()
		print "Exception in getLatestDB"
		sock.close()

def recvFile(sock, filename, size):
        fileObj = open(filename, 'w')
        offset = 0
        while True:
		data = sock.recv((size - offset))
		if len(data) == 0:
			break
		fileObj.write(data)
		offset += len(data)
		if offset >= size:
			break
	fileObj.close()

def getLocalIP():
    s = socket(AF_INET, SOCK_DGRAM)
    s.connect(('google.com', 0))
    return s.getsockname()[0]

def ConfigSectionMap(config, section):
    dict1 = {}
    options = config.options(section)
    for option in options:
        try:
            dict1[option] = config.get(section, option)
            if dict1[option] == -1:
                DebugPrint("skip: %s" % option)
        except:
            print("exception on %s!" % option)
            dict1[option] = None

    return dict1

if __name__== "__main__":
	initBootstrap()
	app.run(host='0.0.0.0', port=80)
