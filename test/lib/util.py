import unittest
from unittest.mock import Mock

from test.lib.const import STREAM_START

from nbxmpp import dispatcher
from nbxmpp.protocol import NS_CLIENT
from nbxmpp.protocol import JID


class StanzaHandlerTest(unittest.TestCase):
    def setUp(self):
        self.dispatcher = dispatcher.XMPPDispatcher()

        # Setup mock client
        self.client = Mock()
        self.client.get_bound_jid.return_value = JID('test@test.test')
        self.client.defaultNamespace = NS_CLIENT
        self.client.Connection = Mock() # mock transport
        self.con = self.client.Connection

        self.dispatcher.PlugIn(self.client)

        # Simulate that we have established a connection
        self.dispatcher.StreamInit()
        self.dispatcher.ProcessNonBlocking(STREAM_START)
