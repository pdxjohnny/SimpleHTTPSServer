#!/usr/bin/python
import os
import sys
import shutil


def update_version_files(version):
    files = {
        "setup.py": ("  version = ", "  version = \'%s\',\n"),
        "SimpleHTTPSServer/SimpleHTTPSServer.py": ("VERSION = ", "VERSION = \"%s\"\n"),
        "SimpleHTTPSServer/index.html": ("\t\t\t<h5>Version ", "\t\t\t<h5>Version %s</h5>\n")
        }
    for name in files:
        read_file = open(name,"rb")
        write_file = open(name + ".tmp","wb")
        for line in read_file:
            if line.startswith(files[name][0]):
                line = files[name][1] % (version, )
            write_file.write( line )
        read_file.close()
        write_file.close()
        shutil.copyfile(name + ".tmp", name)
        if os.path.exists(name + ".tmp"):
            os.remove(name + ".tmp")
    return version

def git_commit(message):
    command = "git commit -am \"%s\"" % (message, )
    return os.system(command)

def git_tag(version, message):
    command = "git tag \"%s\" -m \"%s\"" % (version, message, )
    return os.system(command)

def git_push():
    command = "git push origin master"
    os.system(command)
    command = "git push --tags origin master"
    return os.system(command)

def upload():
    command = "python setup.py sdist upload -r pypi"
    os.system(command)
    if not os.name == 'nt':
        command = "sudo -HE python -m pip install --upgrade SimpleHTTPSServer"
    else:
        command = "python -m pip install --upgrade SimpleHTTPSServer"
    os.system(command)

def main():
    version = sys.argv[1]
    message = sys.argv[2]
    update_version_files( version )
    git_commit( message )
    git_tag(version, message)
    git_push()
    upload()

if __name__ == '__main__':
    main()
