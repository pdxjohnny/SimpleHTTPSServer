#!/bin/python
import os
import sys


def update_version(version):
	return 

def upload():
	command = "python setup.py sdist upload -r pypi"
	os.system(command)
	command = "pip install --upgrade SimpleHTTPSServer"
	os.system(command)

def main():
	update_version( int(sys.argv[1]) )

if __name__ == '__main__':
	main()