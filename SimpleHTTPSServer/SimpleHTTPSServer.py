#! /usr/bin/python
import socket
import json
import urllib
import ssl
import Cookie
import argparse
import thread
import os
import sys
import urllib2
import traceback
import mimetypes
import datetime

VERSION = "0.6.2"
HTTP_VERSION = "HTTP/1.1"

def log( message ):
	print message

class server(object):
	def __init__(self, server_address, RequestHandler, bind_and_activate = True, key = False, crt = False, threading = False ):
		"""
		Takes the server_address ( '0.0.0.0', PORT ) and bind to it.
		If given ssl key and crt files it wraps the socket with them.
		The actions array is a array of ( 'page', function )
		"""
		self.crt = crt
		self.key = key
		self.threading = threading
		self.RequestHandler = RequestHandler
		self.server_address = server_address
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# So that we don't get socket error 98
		# when the server restarts
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

		# If a .key and .crt file are provided make it an SSL socket
		if self.key and self.crt:
			self.socket = self.wrap_socket( self.socket )

		if bind_and_activate:
			self.serve_forever()

	def wrap_socket( self, unwraped_socket ):
		return ssl.wrap_socket( unwraped_socket, keyfile=self.key,  certfile=self.crt )

	def serve_forever( self ):
		self.socket.bind( self.server_address )
		self.socket.listen(10)
		log( "Waiting for connections..." )
		while True:
			try:
				client_socket, client_address = self.socket.accept()
				if self.threading:
					thread.start_new_thread( self.RequestHandler._handle, ( client_socket, client_address ) )
				else:
					self.RequestHandler._handle( client_socket, client_address )
			except ssl.SSLError, e:
				pass
				# log( "SSL ERROR %s" % str( e ), LOG_ERROR )

class handler(object):

	def __init__( self, actions = [] ):
		self.actions = actions

	def _handle( self, client_socket, client_address ):
		# log( "%s - opened connection." % str( client_address ) )
		response = "500 Internal Server Error"
		try:
			data = self._recv( client_socket )
			if data:
				method, page = self._get_request( data )
				data = urllib.unquote( data ).decode('utf8') 
				log( "\'%s\':\'%s\'" % ( method, page ) )
				for action in self.actions:
					variables = self._get_variables( page, action[1] )
					if action[0] == method and variables:
						request = {
							'method': method,
							'page': page,
							'data': data,
							'variables': variables,
							'socket': client_socket
						}
						# log( "%s - \n%s\n" % ( str( client_address ), data) )
						response = action[2]( request )
						break
		except Exception, e:
			log( "\n\n\n\nERROR %s" % str( e ) )
			log( "%s\n\n\n\n" % str( traceback.print_exc() ) )

		if response:
			client_socket.sendall( response )
		
		client_socket.close()
		# log( "%s - closed connection." % str( client_address ) )

	def _get_variables( self, page, action ):
		if page == action:
			return True
		elif page.count('/') >= action.count('/'):
			page = page.split('/')
			action = action.split('/')
			variables = []
			item_num = 0
			for variable in action:
				if len(variable) > 0 and variable[0] is ':':
					variables.append( item_num )
				elif page[item_num] != action[item_num]:
					return False
				item_num += 1
			page_vars = {}
			for position in variables:
				variable = urllib.unquote( page[position] ).decode('utf8') 
				page_vars[ action[position][1:] ] = variable
			if len(page) > len(action):
				page_vars[ action[ variables[-1] ][1:] ] = '/'.join(page[ variables[-1] : ])
			return page_vars
		return False

	def _recv( self, sock ):
		data = sock.recv(4048).strip()
		# Check of a Content-Length, if there is one
		# then data is being uploaded
		content_length = False
		for line in data.split('\r\n'):
			if 'Content-Length' in line:
				content_length = int(line.split(' ')[-1])
		# If theres a Content-Length he now there is
		# a body that is seperated from the headers
		if content_length:
			# Receve until we have all the headers
			# we know we have then wehn we reach the
			# body delim, '\r\n\r\n'
			headers, header_text = self.get_headers( data )
			# Parse the headers so he can use them
			feild_delim = False
			if 'Content-Type' in headers and 'boundary=' in headers['Content-Type']:
				feild_delim = headers['Content-Type'].split('boundary=')[-1]
			# The post_data will be what ever is after the header_text
			post_data = data[ len( header_text ) : ]
			# Remove the header to data break, we will add it back later
			if post_data.find('\r\n\r\n') != -1:
				post_data = "\r\n" + '\r\n\r\n'.join(data.split('\r\n\r\n')[1:])
			# Sometimes feild_delim messes up Content-Length so recive
			# until the last is found otherwise recive the size
			if feild_delim:
				post_data += self._recvall( sock, content_length - len(post_data), feild_delim + '--\r\n' )
			else:
				post_data += self._recvall( sock, content_length - len(post_data) )
			# Merge the headers with the posted data
			data = header_text + "\r\n\r\n" + post_data
		if len(data) < 1:
			return False
		return data

	def get_headers( self, data ):
		headers_as_object = {}
		headers = data
		if data.find('\r\n\r\n') != -1:
			headers = data.split('\r\n\r\n')[0]
		for line in headers.split('\r\n'):
			if line.find(': ') != -1:
				headers_as_object[ line.split(': ')[0] ] = ': '.join(line.split(': ')[1:])
		return headers_as_object, headers

	def _recvall( self, sock, n, end_on = False ):
		data = ''
		while len(data) < n:
			if end_on and data[ -len(end_on): ] == end_on:
				break
			data += sock.recv(n - len(data))
		return data

	def _get_request( self, data ):
		first_line = data.split('\n')[0]
		first_line = first_line.split("/")
		method = first_line[0].replace(' ', '').lower()
		page = '/' + '/'.join(first_line[1:])
		page = 'HTTP'.join(page.split("HTTP")[:-1])
		page = page.replace(' ', '')
		method = urllib.unquote( method ).decode('utf8') 
		page = urllib.unquote( page ).decode('utf8') 
		return method, page

	def create_header( self ):
		headers = {
			HTTP_VERSION: "200 OK",
			"Content-Length": "",
			"Content-Type": "text/html",
			"Server": "SimpleHTTPS/%s Python/%s" % (str(VERSION), str(sys.version).split(" ")[0], ),
			"Date": datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S %Z')
		}
		return headers

	def add_header( self, headers, new_header ):
		headers[ new_header[0] ] = new_header[1]
		return headers

	def end_response( self, headers, data ):
		final = "%s %s\n" % (HTTP_VERSION, headers[HTTP_VERSION],)
		headers["Content-Length"] = len(data)
		for prop in headers:
			if prop != HTTP_VERSION:
				final += "%s: %s\n" % ( prop, str(headers[prop]), )
		final += '\n'
		return final + data

	def cookies( self, data ):
		cookies = []
		lines = data.split('\r\n')
		for line in xrange(0,len(lines)):
			if "Cookie:" in lines[line]:
				c = Cookie.SimpleCookie()
				c.load(lines[line])
				cookies.append(c)
		parts = {}
		for cookie in cookies:
			for attr in cookie:
				parts[attr] = cookie[attr].value
		return parts

	def form_data( self, data ):
		form_data = {}
		headers, header_text = self.get_headers( data )
		# form-data
		if 'multipart/form-data' in headers['Content-Type']:
			if 'boundary=' in headers['Content-Type']:
				feild_delim = headers['Content-Type'].split('boundary=')[-1]
			# Dont take the first one because thats with the headers
			post = feild_delim.join( data.split( feild_delim )[2:] )
			try:
				post = urllib.unquote( post ).decode('utf8')
			except:
				pass
			post = post.split(feild_delim)

			post = [ p.split('\r\n\r\n') for p in post ]

			form_data = {}
			for p in post:
				if len(p) > 1:
					name_start = p[0].find('\"') + 1
					name_end = p[0].find('\"', name_start+1)
					name = p[0][name_start:name_end]
					form_data[ name ] = '\r\n\r\n'.join( p[1:] )[:-4]
			return form_data
		# x-www-form-urlencoded
		else:
			post = urllib.unquote( data.split('\r\n\r\n')[1] ).decode('utf8')
			form_data = {}
			for p in post.split('&'):
				form_data[p.split('=')[0]] = p.split('=')[1]
			return form_data
		return form_data

	def serve_page( self, page ):
		# If this is the root page
		if page == '' or page[-1] == '/':
			page += 'index.html'
		# Get and return the index.html file
		output = self.static_file( page )
		headers = self.create_header()
		headers["Content-Type"] = mimetypes.guess_type( page )[0]
		return self.end_response( headers, output )

	def static_file( self, page ):
		response = '404 Not Found'
		if os.name == 'nt':
			page = page.replace('/','\\')
		try:
			with open( page, 'rb' ) as output:
				response = ''
				for line in output:
					response += line
		except:
			pass
		return response

	def template( self, page, variables ):
		response = '404 Not Found'
		if os.name == 'nt':
			page = page.replace('/','\\')
		try:
			with open( page, 'r' ) as output:
				response = ''
				for line in output:
					for variable in variables:
						found = '{{' + variable + '}}'
						if found in line:
							line = line.split( found )
							line = variables[variable].join( line )
					response += line
		except:
			pass
		return response


class example(handler):
	"""docstring for example"""
	def __init__( self ):
		super(example, self).__init__()
		self.actions = [
			( 'post', '/:any', self.post_echo ),
			( 'post', '/post_file', self.post_response ),
			( 'get', '/user/:username', self.get_user ),
			( 'get', '/post/:year/:month/:day', self.get_post ),
			( 'get', '/:file', self.get_file ) ]
		
	def post_echo( self, request ):
		try:
			output = self.form_data( request['data'] )
		except:
			# print request['data']
			output = {'ERROR': 'parse_error'}
		output = json.dumps( output )
		headers = self.create_header()
		headers = self.add_header( headers, ( "Content-Type", "application/json") )
		return self.end_response( headers, output )
		
	def post_response( self, request ):
		headers = self.create_header()
		headers = self.add_header( headers, ( "Content-Type", "application/octet-stream") )
		return self.end_response( headers, request['post']['file_name'] )
		
	def get_user( self, request ):
		output = self.template( 'user.html', request['variables'] )
		headers = self.create_header()
		return self.end_response( headers, output )
		
	def get_post( self, request ):
		output = json.dumps(request['variables'])
		headers = self.add_header( headers, ( "Content-Type", "application/json") )
		headers = self.create_header()
		return self.end_response( headers, output )

	def get_file( self, request ):
		return self.serve_page( directory + request["page"] )

directory = os.path.dirname(os.path.realpath(__file__)) + '/'

def main():
	address = "0.0.0.0"

	port = 80
	if len( sys.argv ) > 1:
		port = int ( sys.argv[1] )

	http = server( ( address, port ), example(), bind_and_activate = False, threading = True )
	# https = server( ( address, 443 ), example(), bind_and_activate = False, threading = True, key = 'server.key', crt = 'server.crt' )

	# thread.start_new_thread( https.serve_forever, () )
	thread.start_new_thread( http.serve_forever, () )
	raw_input("Return Key to exit\n")


if __name__ == '__main__':
	main()
