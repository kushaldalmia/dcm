#!/usr/bin/env python
import json
import os
import requests 
import sqlite3
import urllib

from flask import Flask, request, session , g, redirect, url_for\
	abort, render_template, flash, response, send_file\
	make_response

#configs
BOOTSTRAP = 'localhost:5000'
REGISTER  = '/register'
SLASH     = '/'
IP 	  = '127.0.0.2'
PORT      = '12345'


def register_node(ip, port):
	data = requests.get('http://' + BOOTSTRAP + REGISTER + SLASH + str(ip) +
					SLASH + str(port) +SLASH);
	ip_list = json.loads(data.text)
	count = ip_list[0]['count']
	my_nodeid = ip_list[0]['my_nodeid']
	ip_list = ip_list[1:]
	return ip_list

	 
if __name__== "__main__":
	data = requests.get('http://' + BOOTSTRAP + REGISTER + SLASH + IP + SLASH  				+ PORT + SLASH, )
	print data
	pass

