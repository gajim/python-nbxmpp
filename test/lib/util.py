import sys
import unittest
from test.lib.const import STREAM_START
from unittest.mock import Mock

from nbxmpp.dispatcher import StanzaDispatcher
from nbxmpp.protocol import JID


class StanzaHandlerTest(unittest.TestCase):
    def setUp(self):
        # Setup mock client
        self.client = Mock()
        self.client.is_websocket = False
        self.dispatcher = StanzaDispatcher(self.client)

        self.client.get_bound_jid.return_value = JID.from_string("test@test.test")

        self.dispatcher.reset_parser()
        self.dispatcher.process_data(STREAM_START)


def raise_all_exceptions(func):
    # Exceptions which are raised from async callbacks
    # in GLib or GTK do not bubble up to the unittest
    # This decorator catches all exceptions and raises them
    # after the unittest
    def func_wrapper(self, *args, **kwargs):

        exceptions = []

        def on_hook(type_, value, tback):
            exceptions.append((type_, value, tback))

        orig_excepthook = sys.excepthook
        sys.excepthook = on_hook
        try:
            result = func(self)
        finally:
            sys.excepthook = orig_excepthook
            if exceptions:
                tp, value, tb = exceptions[0]
                raise tp(value).with_traceback(tb)

        return result

    return func_wrapper
