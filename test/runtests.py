#!/usr/bin/env python3


'''
Runs python-nbxmpp's Test Suite

Unit tests tests will be run on each commit.
'''
from __future__ import print_function

import sys
import unittest
import getopt
verbose = 1

try:
    shortargs = 'hv:'
    longargs = 'help verbose='
    opts, args = getopt.getopt(sys.argv[1:], shortargs, longargs.split())
except getopt.error as msg:
    print(msg)
    print('for help use --help')
    sys.exit(2)
for o, a in opts:
    if o in ('-h', '--help'):
        print('runtests [--help] [--verbose level]')
        sys.exit()
    elif o in ('-v', '--verbose'):
        try:
            verbose = int(a)
        except Exception:
            print('verbose must be a number >= 0')
            sys.exit(2)

# new test modules need to be added manually
modules = ( 'unit.test_xmpp_dispatcher_nb',
            'unit.test_xmpp_transports_nb',
            'unit.test_xmpp_smacks',
            #'unit.test_xmpp_client_nb', gajim.org only supports TLS/SSL connections
            'unit.test_xmpp_transports_nb2',
            'unit.test_xml_vulnerability',
          )

nb_errors = 0
nb_failures = 0

for mod in modules:
    suite = unittest.defaultTestLoader.loadTestsFromName(mod)
    result = unittest.TextTestRunner(verbosity=verbose).run(suite)
    nb_errors += len(result.errors)
    nb_failures += len(result.failures)

sys.exit(nb_errors + nb_failures)
