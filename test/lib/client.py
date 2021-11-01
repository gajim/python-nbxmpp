
from typing import Any
from typing import Optional

import logging

from gi.repository import GLib

from nbxmpp.client import Client

from nbxmpp.const import Mode
from nbxmpp.jid import JID

from nbxmpp.util import Observable


log = logging.getLogger('test')


STREAM_INIT = '''<stream xmlns="jabber:client" xmlns:stream="http://etherx.jabber.org/streams" id="unittest" xml:lang="en" version="1.0" from="unittest.com">'''

class TestConnection(Observable):

    def __init__(self, test_flow) -> None:
        super().__init__(log)
        self._test_flow = test_flow

    def send(self, stanza, now=False):
        self.notify('data-sent', stanza)
        GLib.idle_add(self._on_read_async_finish)

    def _on_read_async_finish(self):
        data = self._test_flow.pop()
        self.notify('data-received', data.replace('\n', ''))



class TestClient(Client):
    def __init__(self, test_flow):
        super().__init__()
        self._mode = Mode.UNITTEST
        self._jid = JID.from_string('testclient@unittest.com/test')
        self._con = TestConnection(test_flow)
        # self._con.subscribe('data-sent', self._on_data_sent)
        self._con.subscribe('data-received', self._on_data_received)
        self._dispatcher.reset_parser()
        self._dispatcher._parser.feed(STREAM_INIT)

        self._current_stanza_id = 0

    def _generate_id(self):
        self._current_stanza_id += 1
        return str(self._current_stanza_id)

    def send_stanza(self,
                    stanza: Any,
                    now: bool = False,
                    callback: Optional[Any] = None,
                    timeout: Optional[int] = None,
                    user_data: Optional[dict[Any, Any]] = None):

        id_ = stanza.get('id')
        if id_ is None:
            id_ = self._generate_id()
            stanza.set('id', id_)

        return super().send_stanza(stanza, now, callback, timeout, user_data)

    @property
    def is_websocket(self):
        return False

    # def _on_data_sent(self, _connection, _signal_name, data):
    #     super()._on_data_received(_connection, _signal_name, data)

