#!/bin/bash

python setup.py sdist upload -r pypi
pip install --upgrade SimpleHTTPSServer

