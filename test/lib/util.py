import unittest
from unittest.mock import Mock

from test.lib.const import STREAM_START

from nbxmpp.dispatcher import StanzaDispatcher
from nbxmpp.protocol import JID


class StanzaHandlerTest(unittest.TestCase):
    def setUp(self):
        # Setup mock client
        self.client = Mock()
        self.client.is_websocket = False
        self.dispatcher = StanzaDispatcher(self.client)

        self.client.get_bound_jid.return_value = JID.from_string('test@test.test')

        self.dispatcher.reset_parser()
        self.dispatcher.process_data(STREAM_START)
