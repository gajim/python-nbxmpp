import sys
import os
import getopt

root = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../..')

# look for modules in the CWD, then gajim/test/lib, then gajim/src,
# then everywhere else
sys.path.insert(1, root)
sys.path.insert(1, root + '/test/lib')

def sortxml(data):
    sorted(data.attrs.keys())
    if data.kids:
        for a in data.kids:
            if not isinstance(a, str):
                sortxml(a)

def setup_env():
    pass
