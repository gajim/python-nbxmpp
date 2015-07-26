#!/usr/bin/python3

import sys
import os
import nbxmpp
import time
import logging
try:
    from gi.repository import GObject as gobject
except Exception:
    import gobject

consoleloghandler = logging.StreamHandler()
root_log = logging.getLogger('nbxmpp')
#root_log.setLevel('DEBUG')
root_log.addHandler(consoleloghandler)

if len(sys.argv) < 2:
    print("Syntax: xsend JID text")
    sys.exit(0)

to_jid = sys.argv[1]
text = ' '.join(sys.argv[2:])

jidparams = {}
if os.access(os.environ['HOME'] + '/.xsend', os.R_OK):
    for ln in open(os.environ['HOME'] + '/.xsend').readlines():
        if not ln[0] in ('#', ';'):
            key, val = ln.strip().split('=', 1)
            jidparams[key.lower()] = val
for mandatory in ['jid', 'password']:
    if mandatory not in jidparams.keys():
        open(os.environ['HOME']+'/.xsend','w').write('#Uncomment fields before use and type in correct credentials.\n#JID=romeo@montague.net/resource (/resource is optional)\n#PASSWORD=juliet\n')
        print('Please point ~/.xsend config file to valid JID for sending messages.')
        sys.exit(0)

class Connection:
    def __init__(self):
        self.jid = nbxmpp.protocol.JID(jidparams['jid'])
        self.password = jidparams['password']
        self.sm = nbxmpp.Smacks(self) # Stream Management
        self.client_cert = None

    def on_auth(self, con, auth):
        if not auth:
            print('could not authenticate!')
            sys.exit()
        print('authenticated using ' + auth)
        self.send_message(to_jid, text)

    def on_connected(self, con, con_type):
        print('connected with ' + con_type)
        auth = self.client.auth(self.jid.getNode(), self.password, resource=self.jid.getResource(), sasl=1, on_auth=self.on_auth)

    def get_password(self, cb, mech):
        cb(self.password)

    def on_connection_failed(self):
        print('could not connect!')

    def _event_dispatcher(self, realm, event, data):
        pass

    def connect(self):
        idle_queue = nbxmpp.idlequeue.get_idlequeue()
        self.client = nbxmpp.NonBlockingClient(self.jid.getDomain(), idle_queue, caller=self)
        self.con = self.client.connect(self.on_connected, self.on_connection_failed, secure_tuple=('tls', '', '', None, None))

    def send_message(self, to_jid, text):
        id_ = self.client.send(nbxmpp.protocol.Message(to_jid, text, typ='chat'))
        print('sent message with id ' + id_)
        gobject.timeout_add(1000, self.quit)

    def quit(self):
        self.disconnect()
        ml.quit()

    def disconnect(self):
        self.client.start_disconnect()


con = Connection()
con.connect()
ml = gobject.MainLoop()
ml.run()
