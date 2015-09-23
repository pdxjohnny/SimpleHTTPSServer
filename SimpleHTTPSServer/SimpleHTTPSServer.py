#! /usr/bin/python
import os
import sys
import ssl
import json
import copy
import socket
import urllib
import Cookie
import thread
import base64
import urllib2
import datetime
import argparse
import traceback
import mimetypes

__version__ = "0.6.98"
PORT = 80
HTTP_VERSION = "HTTP/1.1"
WORKING_DIR = os.getcwd()
LINE_BREAK = u"\r\n"
DOUBLE_LINE_BREAK = LINE_BREAK * 2
ERROR_RESPONSE = ("500 Error", "<h1>500 Internal Server Error</h1>")
AUTH_RESPONSE = ("401 Unauthorized", "<h1>401 Unauthorized</h1>")
SEND_BASIC_AUTH = {
	"method": ("WWW-Authenticate", "Basic"),
	"response": AUTH_RESPONSE[1]
	}


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
		# So that we don't get socket error 98 when the server restarts
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
		self.serving = True
		while self.serving:
			try:
				client_socket, client_address = self.socket.accept()
				if self.threading:
					thread.start_new_thread( self.RequestHandler.start_connection, ( client_socket, client_address ) )
				else:
					self.RequestHandler.start_connection( client_socket, client_address )
			except ssl.SSLError, e:
				pass
				# self.log( "SSL ERROR %s" % str( e ), LOG_ERROR )

class handler(object):

	def __init__( self, actions = [] ):
		self.server_process = False
		self.actions = actions

	def log(self, message):
		del message

	def start(self, host="0.0.0.0", port=PORT, key=False, crt=False, threading=True, **kwargs):
		self.log("Starting on {0}:{1}".format(host, port))
		self.server_process = server((host, port), self, \
			bind_and_activate=False, threading=True, \
			key=key, crt=crt)
		if threading:
			thread.start_new_thread(self.server_process.serve_forever, ())
		else:
			self.server_process.serve_forever()

	def stop(self):
		self.log("Stopping server")
		if self.server_process:
			self.server_process.serving = False
		return True

	def start_connection( self, client_socket, client_address ):
		self.log( "%s - opened connection." % str( client_address ) )
		return self._handle( client_socket, client_address )

	def _handle( self, client_socket, client_address ):
		keep_alive = self.handle_one_request( client_socket, client_address )
		if keep_alive is None:
			keep_alive = False
		while keep_alive:
			keep_alive = self.handle_one_request( client_socket, client_address )
			# handle_one_request can request that the connection be demmed closed
			if keep_alive is None:
				break
		return self.end_connection( client_socket, client_address )

	def end_connection( self, client_socket, client_address ):
		self.log( "%s - closed connection." % str( client_address ) )
		return True

	def handle_one_request( self, client_socket, client_address ):
		found_method = False
		response = False
		authorized = True
		data = False
		try:
			try:
				data = self._recv( client_socket )
			except Exception as error:
				client_socket.close()
				self.log(error)
				self.log("Closed connection")
				return False
			if data:
				method, page = self._get_request( data )
				# data = urllib.unquote( data ).decode('utf8')
				self.log( "\'%s\':\'%s\'" % ( method, page ) )
				for action in self.actions:
					variables = self._get_variables( page, action[1] )
					if action[0] == method and variables:
						found_method = True
						request = {
							'method': method,
							'page': page,
							'data': data,
							'variables': variables,
							'socket': client_socket
						}
						# self.log( "%s - \n%s\n" % ( str( client_address ), data) )
						if len(action) > 3:
							authorized = action[3]( request )
						if type(authorized) is bool and authorized is True:
							response = action[2]( request )
						break
		except Exception, e:
			self.log( "\n\n\n\nERROR %s" % str( e ) )
			found_method = False

		if not found_method:
			headers = self.create_header()
			headers[HTTP_VERSION] = ERROR_RESPONSE[0]
			response = self.end_response( headers, ERROR_RESPONSE[1] )
		elif type(authorized) is dict:
			headers = self.create_header()
			headers[HTTP_VERSION] = AUTH_RESPONSE[0]
			headers[authorized["method"][0]] = authorized["method"][1]
			response = self.end_response( headers, authorized["response"] )

		if response:
			client_socket.sendall( response )

		if response is None:
			return response

		if data:
			headers = self.get_headers( data )
			if not "Connection" in headers or headers["Connection"].lower() != "keep-alive":
				client_socket.close()
				self.log("No Connection Header")
				self.log("Closed connection")
				return False
		else:
			client_socket.close()
			self.log("No data")
			self.log("Closed connection")
			return False
		return response
		# self.log( "%s - closed connection." % str( client_address ) )

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
		data = sock.recv(4048)
		# Check of a Content-Length, if there is one
		# then data is being uploaded
		content_length = False
		for line in data.split(LINE_BREAK):
			if 'Content-Length' in line:
				content_length = int(line.split(' ')[-1])
				break
		# If theres a Content-Length he now there is
		# a body that is seperated from the headers
		if content_length:
			# Receve until we have all the headers
			# we know we have then wehn we reach the
			# body delim, DOUBLE_LINE_BREAK
			headers, header_text = self.get_headers(data, text=True)
			# Parse the headers so he can use them
			feild_delim = False
			if 'Content-Type' in headers and 'boundary=' in headers['Content-Type']:
				feild_delim = headers['Content-Type'].split('boundary=')[-1]
			# The post_data will be what ever is after the header_text
			post_data = data[ len( header_text ) : ]
			# Remove the header to data break, we will add it back later
			if post_data.find(DOUBLE_LINE_BREAK) != -1:
				post_data = LINE_BREAK + DOUBLE_LINE_BREAK.join(data.split(DOUBLE_LINE_BREAK)[1:])
			# Sometimes feild_delim messes up Content-Length so recive
			# until the last is found otherwise recive the size
			if feild_delim:
				post_data += self._recvall( sock, content_length - len(post_data.lstrip()), feild_delim + '--\r\n' )
			else:
				post_data += self._recvall( sock, content_length - len(post_data.lstrip()) )
			# Merge the headers with the posted data
			data = header_text + DOUBLE_LINE_BREAK + post_data
		if len(data) < 1:
			return False
		return data

	def get_headers( self, data, text=False ):
		headers_as_object = {}
		headers = data
		if data.find(DOUBLE_LINE_BREAK) != -1:
			headers = data.split(DOUBLE_LINE_BREAK)[0]
		for line in headers.split(LINE_BREAK):
			if line.find(': ') != -1:
				headers_as_object[ line.split(': ')[0] ] = ': '.join(line.split(': ')[1:])
		if text:
			return headers_as_object, headers
		return headers_as_object

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
			"Content-Length": 0,
			"Content-Type": "text/html",
			"Connection": "keep-alive",
			"Server": "SimpleHTTPS/%s Python/%s" % (str(__version__), str(sys.version).split(" ")[0], ),
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
		lines = data.split(LINE_BREAK)
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
		headers = self.get_headers( data )
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

			post = [ p.split(DOUBLE_LINE_BREAK) for p in post ]

			form_data = {}
			for p in post:
				if len(p) > 1:
					name_start = p[0].find('\"') + 1
					name_end = p[0].find('\"', name_start+1)
					name = p[0][name_start:name_end]
					form_data[ name ] = DOUBLE_LINE_BREAK.join( p[1:] )[:-4]
			return form_data
		# x-www-form-urlencoded
		else:
			post = data.split(DOUBLE_LINE_BREAK)[1][2:]
			form_data = {}
			for p in post.split('&'):
				key = urllib.unquote(p.split('=')[0]).decode('utf8')
				value = urllib.unquote(p.split('=')[1]).decode('utf8')
				form_data[key] = value
			return form_data
		return form_data

	def serve_page( self, page, request=False ):
		# If this is the root page
		if page == '' or page[-1] == '/':
			page += 'index.html'
		# Get and return the index.html file
		output = self.static_file( page )
		headers = self.create_header()
		headers["Content-Type"] = mimetypes.guess_type( page )[0]
		return self.end_response( headers, output )

	def static_file( self, page, request=False ):
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

	def template( self, page, variables, request=False ):
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

	def basic_auth( self, request, response=AUTH_RESPONSE[1] ):
		headers = self.get_headers(request["data"])
		send_basic_auth = copy.deepcopy(SEND_BASIC_AUTH)
		send_basic_auth["response"] = response
		if "Authorization" in headers:
			auth = headers["Authorization"].split()[-1]
			auth = base64.b64decode(auth)
			return True, auth.split(":")
		return False, send_basic_auth


class example(handler):
	"""docstring for example"""
	def __init__( self ):
		super(example, self).__init__()
		self.actions = [
			( 'post', '/:any', self.post_echo ),
			( 'post', '/post_file', self.post_response ),
			( 'get', '/user/:username', self.get_user ),
			( 'get', '/post/:year/:month/:day', self.get_post ),
			( 'get', '/:file', self.get_file )
			]

	def auth( self, request ):
		authorized, response = self.basic_auth(request)
		if not authorized:
			return response
		username, password = response
		return True

	def post_echo( self, request ):
		try:
			output = self.form_data( request['data'] )
		except:
			output = {'ERROR': 'parse_error'}
		output = json.dumps( output )
		headers = self.create_header()
		headers["Content-Type"] = "application/json"
		return self.end_response( headers, output )

	def post_response( self, request ):
		headers = self.create_header()
		headers["Content-Type"] = "application/octet-stream"
		return self.end_response( headers, request['post']['file_name'] )

	def get_user( self, request ):
		output = self.template( 'user.html', request['variables'] )
		headers = self.create_header()
		return self.end_response( headers, output )

	def get_post( self, request ):
		output = json.dumps(request['variables'])
		headers["Content-Type"] = "application/json"
		headers = self.create_header()
		return self.end_response( headers, output )

	def get_file( self, request ):
		return self.serve_page( WORKING_DIR + request["page"] )

def main():
	address = "0.0.0.0"

	port = PORT
	if len( sys.argv ) > 1:
		port = int ( sys.argv[1] )

	http = server( ( address, port ), example(), bind_and_activate = False, threading = True )
	# https = server( ( address, 443 ), example(), bind_and_activate = False, threading = True, key = 'server.key', crt = 'server.crt' )

	# thread.start_new_thread( https.serve_forever, () )
	thread.start_new_thread( http.serve_forever, () )
	raw_input("Return Key to exit\n")


if __name__ == '__main__':
	main()
