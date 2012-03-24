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
        with closing(connect_db()) as db:
                with app.open_resource('schema.sql') as f:
			print f
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
	
## Register the IP and Port for the server, and assign it an ID.
# if the server:port is already registered, then return the previously assigned
# id.
@app.route("/register/<ip_add>/<port_no>/", methods =['GET','POST'])
def register(ip_add=None, port_no=None):
	print 50 * '-'
	print "request received to register \n Ip: " + ip_add + "\n Port :" + port_no
	print 50 * '-'
	db_str = ip_add.strip() + ":" + port_no.strip()
	
	is_new = False 

	# See if the IP:PORT is already registered 
	id_list = query_db('select node_id from NodeMap where ip_port=?',[db_str])
	print id_list
	node_id = 0
	
	if id_list == []:
		# This means we have a new member being registered
		is_new = True
		
		# now register the new guy into the NodeMap table
		try :
			print "Inserting the Node into NodeMap"
			g.db.execute('insert into NodeMap (ip_port)'\
				' values (?)',
				[db_str])
			g.db.commit()
			node_list = query_db('select node_id from NodeMap where ip_port=?',
				[db_str])
			node_id = node_list[0]['node_id']
			print "node id is "
			print node_id

		except sqlite3.IntegrityError:
			print "DUPLICATE ENTRY: Node already registered"

		except sqlite3.OperationalError, msg:
			print "Operational error "
			print msg	

		except  :
			print "DBINSERT_FAIL: some issue while registering new node"

	else :
		# Now we know that this node was already registered 
		print " DUP_REGREQ:The node with ip "+ ip_add + " has  id\
			 :" + str(id_list[0]['node_id'])
		node_id = id_list[0]['node_id']

	# Need to find out How many entries does the Nodes table has
	no_entries = query_db('select Count(*) from Nodes')
	no_entries = no_entries[0]['Count(*)']
	nodes_entries = query_db('SELECT * FROM Nodes where node_id!=? ORDER BY ref_count',
				[node_id])
	ref_count = 0
	
	# Now that we have the entries in the database, lets put our entry
	# into the database
	if is_new :
		ref_count = 0	
	
		# Insert this NEW entry into the database
		try:
			g.db.execute('insert into Nodes (node_id, ref_count, ip_add, port)\
					values (?,?,?,?)', 
					[node_id, ref_count,ip_add, port_no] )
			g.db.commit()		
		except :
			print "NODE_INSERT_ERR: issue while inserting node into database"
			pass

                # we might never need the follwing.	
		# Happens only when some node tries to re-register
		# Will be a @TODO item
#	else :
#
#		tmp_results = query_db('select ref_count from Nodes where port=? and ip_add=?',
#				[int(port_no),ip_add])
#		if tmp_results == []:
#			ref_count = 0;
#		else : 
#			ref_count = int(tmp_results[0]['ref_count']) + 1;
#		
#		# Update the already existing entry in the table

	
	print nodes_entries
	if no_entries == 0:
		dict = [{}]
		return json.dumps(dict)

	elif no_entries <= 3:
		dict = [{}]
		cnt = 0
		for node in nodes_entries:
			cnt = cnt + 1
			print node
			dict.append({})
			dict[cnt]['ip_add'] = node['ip_add']
			dict[cnt]['port']  = node['port']
			# update the refcount of the existing entry
			tmp_results = query_db('select ref_count from Nodes where port=? and ip_add=?',
					[node['port'],node['ip_add']])
			refcount = 0;
			print " TMP RES"
			print tmp_results

			if tmp_results == []:
				refcount = 0;
			else : 
				refcount = int(tmp_results[0]['ref_count']) + 1;
			print "Refcount is : "
			print refcount
			try :
				g.db.execute('update Nodes set ref_count=? where port=? and ip_add=?',
						[refcount, int(node['port']), str(node['ip_add'])])
				g.db.commit()	
				g.db.execute('update Nodes set ref_count=? where port=? and ip_add =?',\
					[no_entries, str(port_no), str(ip_add)] )
				g.db.commit()	
			except :
				print "ERROR while updating refcount !"
				return  "SVR_ERR"

		return json.dumps(dict)
	else:
		dict = [{}]
		cnt = 0
		for node in nodes_entries:
			cnt = cnt + 1
			print node
			dict.append({})
			dict[cnt]['ip_add'] = node['ip_add']
			dict[cnt]['port']  = node['port']
			# update the refcount of the existing entry
			tmp_results = query_db('select ref_count from Nodes where port=? and ip_add=?',
					[node['port'],node['ip_add']])
			if tmp_results == []:
				refcount = 0;
			else : 
				refcount = int(tmp_results[0]['ref_count']) + 1;
			print "Refcount is : "
			print refcount
			try :
				g.db.execute('update Nodes set ref_count=? where port=? and ip_add=?',
						[refcount, int(node['port']), str(node['ip_add'])])
				g.db.commit()	
				g.db.execute('update Nodes set ref_count=? where port=? and ip_add =?',\
					[3, str(port_no), str(ip_add)] )
				g.db.commit()	
			except :
				print "ERROR while updating refcount !"
				return  "SVR_ERR"


			if cnt == 3:
				return json.dumps(dict)

	
	g.db.commit()
	return db_str
	
@app.route("/unregister/<remote_ip>/<remote_port>/<ip_add>/<port_no>/")
def unregister(remote_ip=None, remote_port=None, ip_add=None, port_no=None):
	db_str = ip_add.strip() + ":" + port_no.strip()
	print db_str
	id_list = query_db('select node_id from NodeMap where ip_port=?',[db_str])
	
	if id_list == []:
		print "Node is not in the database "
		return json.dumps("FAIL")
	else :
		try:
			query_db('delete from NodeMap where ip_port=?',[db_str])
			g.db.commit()	
			query_db('delete from Nodes where ip_add=? and port=?',[str(ip_add), str(port_no)])
			g.db.commit()	

			node_entry = query_db('select ref_count from Nodes where ip_add=? and port=?', [str(remote_ip), str(remote_port)]) 

			print 30 * '-'
			print node_entry
			print 30 * '-'

			if node_entry == []:
				print "Node not found "
				return json.dumps("IGNORE")

			else :
				refcnt = node_entry[0]['ref_count']
				print "Previous refcount + " + str(refcnt)
				refcnt = int(refcnt) -1;
				print "After updating  " + str(refcnt)
				try :
					g.db.execute('update Nodes set ref_count=? where port=? and ip_add=?',\
						[str(refcnt), str(remote_port), str(remote_ip)] )
					g.db.commit()	
				except :
					print "DB_UPDATE ERROR "
					return json.dumps("UPDATE_ERR")	
				
		except:
			print "DB_DELETE Error!"
			return json.dumps("FAIL")
	
	return json.dumps("END");

if __name__== "__main__":

        if len(sys.argv) > 1 and sys.argv[1].strip() == 'init_db': init_db()
        if len(sys.argv) > 1 and sys.argv[1].strip() == 'remake_db': pass
	app.run(host='0.0.0.0' )

