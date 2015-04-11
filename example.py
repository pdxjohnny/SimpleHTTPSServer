#! /usr/bin/python
import SimpleHTTPSServer
import thread
import json


class example(SimpleHTTPSServer.handler):
	"""docstring for example"""
	def __init__( self ):
		super(example, self).__init__()
		self.actions = [ ( 'post', '/', self.post_response ),
			( 'get', '/user/:username', self.get_user ),
			( 'get', '/', self.index ),
			( 'get', '/:file', self.get_file ) ]
		
	def post_response( self, method, page, data, variables ):
		form_data = self.form_data( data )
		output = json.dumps(form_data)
		headers = self.create_header()
		headers = self.add_header( headers, ( "Content-Type", "application/json") )
		return self.end_response( headers, output )
		
	def get_user( self, method, page, data, variables ):
		output = self.template( 'user.html', variables )
		headers = self.create_header()
		headers = self.add_header( headers, ( "Content-Type", "text/html") )
		return self.end_response( headers, output )

	def get_file( self, method, page, data, variables ):
		output = self.static_file( variables['file'] )
		headers = self.create_header()
		headers = self.add_header( headers, ( "Content-Type", "text/html") )
		return self.end_response( headers, output )
		
	def index( self, method, page, data, variables ):
		output = self.static_file( "index.html" )
		headers = self.create_header()
		headers = self.add_header( headers, ( "Content-Type", "text/html") )
		return self.end_response( headers, output )


def main():
	address = "0.0.0.0"

	http = SimpleHTTPSServer.server( ( address, 80 ), example(), bind_and_activate = False, threading = True )
	https = SimpleHTTPSServer.server( ( address, 443 ), example(), bind_and_activate = False, threading = True, key = 'server.key', crt = 'server.crt' )

	thread.start_new_thread( http.serve_forever, () )
	https.serve_forever()

if __name__ == '__main__':
	main()
