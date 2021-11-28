# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

import logging

from typing import Any, cast
import typing

from gi.repository import Soup
from gi.repository import GLib
from gi.repository import Gio

from nbxmpp.const import TCPState
from nbxmpp.const import ConnectionType
from nbxmpp.util import get_websocket_close_string
from nbxmpp.util import convert_tls_error_flags
from nbxmpp.connection import Connection
from nbxmpp.queue import WebsocketElementQueue

if typing.TYPE_CHECKING:
    from nbxmpp import types

log = logging.getLogger('nbxmpp.websocket')


class WebsocketConnection(Connection, WebsocketElementQueue):
    def __init__(self, *args, **kwargs):
        Connection.__init__(self, *args, **kwargs)
        WebsocketElementQueue.__init__(self)

        self._session = Soup.Session()
        self._session.props.ssl_strict = False

        if self._log.getEffectiveLevel() == logging.INFO:
            self._session.add_feature(
                Soup.Logger.new(Soup.LoggerLogLevel.BODY, -1))

        self._websocket = cast(Soup.WebsocketConnection, None)
        self._cancellable = Gio.Cancellable()

        self._input_closed = False
        self._output_closed = False

    def connect(self):
        self._log.info('Try to connect to %s', self._address.uri)

        self.state = TCPState.CONNECTING

        message = Soup.Message.new('GET', self._address.uri)
        if message is None:
            raise ValueError('invalid uri: %s' % self._address.uri)

        message.connect('starting', self._check_certificate)
        message.set_flags(Soup.MessageFlags.NO_REDIRECT)
        self._session.websocket_connect_async(message,
                                              None,
                                              ['xmpp'],
                                              self._cancellable,
                                              self._on_connect,
                                              None)

    def _on_connect(self,
                    session: Soup.Session,
                    result: Gio.AsyncResult,
                    _user_data: Any):

        # TODO: check if protocol 'xmpp' is set
        try:
            websocket = session.websocket_connect_finish(result)
        except GLib.Error as error:
            quark = GLib.quark_try_string('g-io-error-quark')
            if error.matches(quark, Gio.IOErrorEnum.CANCELLED):
                self._finalize('disconnected')
                return

            self._log.info('Connection Error: %s', error)
            self._finalize('connection-failed')
            return

        websocket.set_keepalive_interval(5)
        websocket.connect('message', self._on_websocket_message)
        websocket.connect('closed', self._on_websocket_closed)
        websocket.connect('closing', self._on_websocket_closing)
        websocket.connect('error', self._on_websocket_error)
        websocket.connect('pong', self._on_websocket_pong)

        self._websocket = websocket
        self.state = TCPState.CONNECTED
        self.notify('connected')

    def start_tls_negotiation(self):
        # Soup.Session does this automatically
        raise NotImplementedError

    def _check_certificate(self, message: Soup.Message):
        https_used, certificate, errors = message.get_https_status()
        if not https_used and self._address.type == ConnectionType.PLAIN:
            return

        self._peer_certificate = certificate
        self._peer_certificate_errors = convert_tls_error_flags(errors)

        self.notify('certificate-set')

        if self._accept_certificate():
            return

        self.notify('bad-certificate')
        self._cancellable.cancel()

    def _on_websocket_message(self,
                              _websocket: Soup.WebsocketConnection,
                              _type: int,
                              message: GLib.Bytes):

        data = message.get_data().decode()
        self._log_stanza(data)

        if self._input_closed:
            self._log.warning('Received data after stream closed')
            return

        self.notify('data-received', data)

    def _on_websocket_pong(self,
                           _websocket: Soup.WebsocketConnection,
                           _message: GLib.Bytes):
        self._log.info('Pong received')

    def _on_websocket_closed(self, websocket: Soup.WebsocketConnection):
        self._log.info('Closed %s', get_websocket_close_string(websocket))
        self._finalize('disconnected')

    def _on_websocket_closing(self, _websocket: Soup.WebsocketConnection):
        self._log.info('Closing')

    def _on_websocket_error(self,
                            _websocket: Soup.WebsocketConnection,
                            error: GLib.Error):
        self._log.error(error)
        if self._state not in (TCPState.DISCONNECTED, TCPState.DISCONNECTING):
            self._finalize('disconnected')

    def send(self, element: types.Base, now: bool = False):
        if self._state in (TCPState.DISCONNECTED, TCPState.DISCONNECTING):
            self._log.warning('send() not possible in state: %s', self._state)
            return

        data = element.tostring()
        self._websocket.send_text(data)
        self._log_stanza(data, received=False)
        self.notify('data-sent', element)

    def disconnect(self):
        if self._state == TCPState.CONNECTING:
            self.state = TCPState.DISCONNECTING
            self._cancellable.cancel()
            return

        if self._state in (TCPState.DISCONNECTED, TCPState.DISCONNECTING):
            self._log.warning('Called disconnect on state: %s', self._state)
            return

        self._websocket.close(Soup.WebsocketCloseCode.NORMAL, None)
        self.state = TCPState.DISCONNECTING

    def _check_for_shutdown(self):
        if self._input_closed and self._output_closed:
            self._websocket.close(Soup.WebsocketCloseCode.NORMAL, None)

    def shutdown_input(self):
        self._log.info('Shutdown input')
        self._input_closed = True
        self._check_for_shutdown()

    def shutdown_output(self):
        self.state = TCPState.DISCONNECTING
        self._log.info('Shutdown output')
        self._output_closed = True

    def _finalize(self, signal_name: str):
        self._input_closed = True
        self._output_closed = True
        self.state = TCPState.DISCONNECTED
        self.notify(signal_name)
        self.destroy()

    def destroy(self):
        super().destroy()
        self._session.abort()
        self._session = cast(Soup.Session, None)
        self._websocket = cast(Soup.WebsocketConnection, None)
