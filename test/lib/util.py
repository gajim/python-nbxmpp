import unittest
from unittest.mock import Mock

from gi.repository import GLib

from test.lib.const import STREAM_START

from nbxmpp.dispatcher import StanzaDispatcher
from nbxmpp.jid import JID


class StanzaHandlerTest(unittest.TestCase):
    def setUp(self):
        # Setup mock client
        self.client = Mock()
        self.client.is_websocket = False
        self.dispatcher = StanzaDispatcher(self.client)

        self.client.get_bound_jid.return_value = JID.from_string('test@test.test')

        self.dispatcher.reset_parser()
        self.dispatcher.process_data(STREAM_START)


def iterate_mainloop():
    main_context = GLib.MainContext.default()
    while main_context.pending():
        main_context.iteration(False)
