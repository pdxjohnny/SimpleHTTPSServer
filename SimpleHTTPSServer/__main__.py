import sys
import time
import thread
import SimpleHTTPSServer

def main():
    address = "0.0.0.0"

    port = 80
    if len( sys.argv ) > 1:
        port = int ( sys.argv[1] )

    http = SimpleHTTPSServer.server( ( address, port ), SimpleHTTPSServer.example(), bind_and_activate = False, threading = True )
    # https = SimpleHTTPSServer.server( ( address, 443 ), SimpleHTTPSServer.example(), bind_and_activate = False, threading = True, key = 'server.key', crt = 'server.crt' )

    # thread.start_new_thread( https.serve_forever, () )
    thread.start_new_thread( http.serve_forever, () )
    print("Serving HTTP")
    while True:
        time.sleep(300)


if __name__ == '__main__':
    main()
