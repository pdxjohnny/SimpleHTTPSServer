#! /usr/bin/python
import socket
import json
import urllib
import ssl
import Cookie
import argparse
import thread

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

		# If a .key and .crt file are provided make it an SSL socket
		if self.key and self.crt:
			self.socket = ssl.wrap_socket(self.socket, keyfile=self.key, certfile=self.crt, cert_reqs=ssl.CERT_NONE)

		if bind_and_activate:
			self.serve_forever()

	def serve_forever( self ):
		self.socket.bind( self.server_address )
		self.socket.listen(10)
		print "Waiting for connections..."
		while True:
			client_socket, client_address = self.socket.accept()
			if self.threading:
				thread.start_new_thread( self.RequestHandler._handle, ( client_socket, client_address ) )
			else:
				self.RequestHandler._handle( client_socket, client_address )

class handler(object):

	def __init__( self, actions = [] ):
		self.actions = actions

	def _handle( self, client_socket, client_address ):
		# print "Reciving from", client_address
		response = "500 Internal Server Error"
		try:
			data = self._recv( client_socket )

			if data:
				method, page = self._get_request( data )
				print "\'%s\':\'%s\'" % ( method, page )
				for action in self.actions:
					variables = self._get_variables( page, action[1] )
					if action[0] == method and variables:
						response = action[2]( method, page, data, variables )
						break
		except Exception, e:
			print "ERROR", e

		client_socket.sendall( response )
		
		client_socket.close()
		# print client_address, "- closed connection."

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
				page_vars[ action[position][1:] ] = page[position]
			if len(page) > len(action):
				page_vars[ action[ variables[-1] ][1:] ] = '/'.join(page[ variables[-1] : ])
			return page_vars
		return False

	def _recv( self, sock ):
		msg = sock.recv(4048).strip()
		if len(msg) < 1:
			return False
		return msg

	def _recvall( self, sock, n ):
		data = ''
		while len(data) < n:
			packet = sock.recv(n - len(data))
			if not packet:
				return False
			data += packet
		return data

	def _get_request( self, data ):
		first_line = data.split('\n')[0]
		first_line = first_line.split("/")
		method = first_line[0].replace(' ', '').lower()
		page = '/' + '/'.join(first_line[1:]).split("HTTP")[0].replace(' ', '')
		return method, page

	def create_header( self ):
		headers = {
			"HTTP/1.1": "200 OK",
			"Content length": "",
			"Content-Type": "text/html"
		}
		return headers

	def add_header( self, headers, new_header ):
		headers[ new_header[0] ] = new_header[1]
		return headers

	def end_response( self, headers, data ):
		final = "HTTP/1.1 %s\n" % headers["HTTP/1.1"]
		final += "Content length %d\n" % len(data)
		for prop in headers:
			if prop != "HTTP/1.1" and prop != "Content length":
				final += "%s: %s\n" % ( prop, headers[prop] )
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
		# form-data
		if data.find('Content-Disposition: form-data; ') > -1:
			form_data = ''.join(data.split('Content-Disposition: form-data; ')[1:])
			post = urllib.unquote( form_data ).decode('utf8').split('\r\n')
			form_data = []
			for p in post:
				if not len(p) < 1 and not p.startswith("-"):
					form_data.append(p)
			post = form_data
			form_data = {}
			p = 0
			while p < len(post):
				form_data[ post[p].split('name=\"')[1][:-1] ] = post[p+1]
				p += 2
			return form_data
		# x-www-form-urlencoded
		else:
			post = urllib.unquote( data.split('\r\n\r\n')[1] ).decode('utf8')
			form_data = {}
			for p in post.split('&'):
				form_data[p.split('=')[0]] = p.split('=')[1]
			return form_data
		return form_data


class static(handler):
	"""docstring for static"""
	def __init__( self ):
		super(static, self).__init__()
		self.actions = [ ( 'post', '/', self.post_response ),
			( 'get', '/user/:username', self.get_user ),
			( 'get', '/:dir', self.index ) ]
		
	def post_response( self, method, page, data, variables ):
		form_data = self.form_data( data )
		output = json.dumps(form_data)
		headers = self.create_header()
		headers = self.add_header( headers, ( "Content-Type", "application/json") )
		return self.end_response( headers, output )
		
	def get_user( self, method, page, data, variables ):
		output = json.dumps(variables)
		headers = self.create_header()
		headers = self.add_header( headers, ( "Content-Type", "application/json") )
		return self.end_response( headers, output )
		
	def index( self, method, page, data, variables ):
		output = "Welcome"
		headers = self.create_header()
		headers = self.add_header( headers, ( "Content-Type", "text/html") )
		return self.end_response( headers, output )


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("-l", help="Logs all actions of server and connections")
	parser.add_argument("-p", help="Sets the port to bind to, 80")
	parser.add_argument("-a", help="Sets the address to bind to, 0.0.0.0")
	args = parser.parse_args()

	address = "0.0.0.0"
	port = 80
	# if args.p:
	# 	port = int( args.p )
	# if args.s
	# 	address = int( args.s )

	run_server = server( ( address, port ), static(), threading = True )

if __name__ == '__main__':
	main()
