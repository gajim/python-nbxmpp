#!/usr/bin/python3

import sys
import os
import logging

import nbxmpp
from nbxmpp.const import Realm
from nbxmpp.const import Event
from gi.repository import GLib

if sys.platform in ('win32', 'darwin'):
    import certifi

consoleloghandler = logging.StreamHandler()
log = logging.getLogger('nbxmpp')
log.setLevel('INFO')
log.addHandler(consoleloghandler)

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
        self.client_cert = None
        self.idle_queue = nbxmpp.idlequeue.get_idlequeue()
        self.client = None

    def _on_auth_successful(self):
        print('authenticated')
        self.client.bind()

    def _on_connection_active(self):
        print('Connection active')
        self.client.RegisterHandler('message', self._on_message)
        self.send_presence()

    def _on_auth_failed(self, reason, text):
        log.debug("Couldn't authenticate")
        log.error(reason, text)
        exit()

    def _on_message(self, con, stanza):
        print('message received')
        print(stanza.getBody())

    def _on_connected(self, con, con_type):
        print('connected with ' + con_type)
        self.client.auth(self.jid.getNode(),
                         get_password=self._get_password,
                         resource=self.jid.getResource())

    def _get_password(self, mech, password_cb):
        password_cb(self.password)

    def _on_connection_failed(self):
        print('could not connect!')

    def _event_dispatcher(self, realm, event, data):
        if realm == Realm.CONNECTING:
            if event == Event.AUTH_SUCCESSFUL:
                log.info(event)
                self._on_auth_successful()

            elif event == Event.AUTH_FAILED:
                log.error(event)
                log.error(data)
                self._on_auth_failed(*data)

            elif event == Event.SESSION_FAILED:
                log.error(event)

            elif event == Event.BIND_FAILED:
                log.error(event)

            elif event == Event.CONNECTION_ACTIVE:
                log.info(event)
                self._on_connection_active()
            return

    def connect(self):
        cacerts = ''
        if sys.platform in ('win32', 'darwin'):
            cacerts = certifi.where()

        self.client = nbxmpp.NonBlockingClient(self.jid.getDomain(),
                                               self.idle_queue,
                                               caller=self)

        self.client.connect(self._on_connected,
                            self._on_connection_failed,
                            secure_tuple=('tls', cacerts, '', None, None, False))

        if sys.platform == 'win32':
            timeout, in_seconds = 20, None
        else:
            timeout, in_seconds = 100, False

        if in_seconds:
            GLib.timeout_add_seconds(timeout, self.process_connections)
        else:
            GLib.timeout_add(timeout, self.process_connections)

    def send_presence(self):
        presence = nbxmpp.Presence()
        self.client.send(presence)

    def quit(self):
        self.disconnect()
        ml.quit()

    def disconnect(self):
        self.client.start_disconnect()

    def process_connections(self):
        try:
            self.idle_queue.process()
        except Exception:
            # Otherwise, an exception will stop our loop

            if sys.platform == 'win32':
                # On Windows process() calls select.select(), so we need this
                # executed as often as possible.
                timeout, in_seconds = 1, None
            else:
                timeout, in_seconds = 100, False

            if in_seconds:
                GLib.timeout_add_seconds(timeout, self.process_connections)
            else:
                GLib.timeout_add(timeout, self.process_connections)
            raise
        return True # renew timeout (loop for ever)


con = Connection()
con.connect()
ml = GLib.MainLoop()
ml.run()
