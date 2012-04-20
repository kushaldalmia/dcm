#!/usr/bin/env python
from flask import Flask,flash, request,render_template, Response,session,g
from flask import Flask, request, session, g, redirect, url_for, \
                  abort, render_template, flash, Response, send_file
from contextlib import closing
import json
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
MAX_PEERS = 3

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
	
@app.route("/unregister/<remote_ip>/<remote_port>/<ip_add>/<port_no>/")
def unregister(remote_ip=None, remote_port=None, ip_add=None, port_no=None):
	failed_node_id = ip_add.strip() + ":" + port_no.strip()
	neighbor_node_id = remote_ip.strip() + ":" + remote_port.strip()
	
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

if __name__== "__main__":
        init_db()
	app.run(host='0.0.0.0')
