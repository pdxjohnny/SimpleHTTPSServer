import os
import sys
import time
import thread

import SimpleHTTPSServer
from SimpleExampleServer import SimpleChat
from SimpleWebSocketServer import SimpleWebSocketServer

WORKING_DIR = os.getcwd()

class example(SimpleHTTPSServer.handler):
	"""docstring for example"""
	def __init__( self ):
		super(example, self).__init__()
		self.actions = [
			( 'post', '/:any', self.post_echo ),
			( 'post', '/post_file', self.post_response ),
			( 'get', '/sock', SimpleWebSocketServer(SimpleChat) ),
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

    port = 80
    if len( sys.argv ) > 1:
        port = int ( sys.argv[1] )

    http = SimpleHTTPSServer.server( ( address, port ), example(), bind_and_activate = False, threading = True )
    # https = SimpleHTTPSServer.server( ( address, 443 ), SimpleHTTPSServer.example(), bind_and_activate = False, threading = True, key = 'server.key', crt = 'server.crt' )

    # thread.start_new_thread( https.serve_forever, () )
    thread.start_new_thread( http.serve_forever, () )
    print("Serving HTTP")
    while True:
        time.sleep(300)


if __name__ == '__main__':
    main()
