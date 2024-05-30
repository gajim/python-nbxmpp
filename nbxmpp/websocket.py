# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

import logging

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Soup

from nbxmpp.connection import Connection
from nbxmpp.const import TCPState
from nbxmpp.http import DEFAULT_USER_AGENT
from nbxmpp.protocol import Protocol
from nbxmpp.util import convert_tls_error_flags
from nbxmpp.util import get_websocket_close_string

log = logging.getLogger("nbxmpp.websocket")


class WebsocketConnection(Connection):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        Connection.__init__(self, *args, **kwargs)

        self._session = Soup.Session()
        self._session.set_user_agent(DEFAULT_USER_AGENT)

        if self._log.getEffectiveLevel() == logging.INFO:
            self._session.add_feature(Soup.Logger.new(Soup.LoggerLogLevel.BODY))

        self._websocket: Soup.WebsocketConnection | None = None
        self._cancellable = Gio.Cancellable()

        self._input_closed = False
        self._output_closed = False

    def connect(self) -> None:
        assert self._address is not None
        self._log.info("Try to connect to %s", self._address.uri)

        self.state = TCPState.CONNECTING

        message = Soup.Message.new("GET", self._address.uri)
        assert message is not None
        message.connect("accept-certificate", self._check_certificate)
        message.connect("notify::tls-peer-certificate", self._on_certificate_set)
        message.connect("network-event", self._on_network_event)
        message.set_flags(Soup.MessageFlags.NO_REDIRECT)
        assert self._session is not None
        self._session.websocket_connect_async(
            message,
            None,
            ["xmpp"],
            GLib.PRIORITY_DEFAULT,
            self._cancellable,
            self._on_connect,
            None,
        )

    def _on_connect(
        self, session: Soup.Session, result: Gio.AsyncResult, _user_data: None
    ) -> None:
        # TODO: check if protocol 'xmpp' is set
        try:
            self._websocket = session.websocket_connect_finish(result)
        except GLib.Error as error:
            quark = GLib.quark_try_string("g-io-error-quark")
            if error.matches(quark, Gio.IOErrorEnum.CANCELLED):
                self._finalize("disconnected")
                return

            self._log.info("Connection Error: %s", error)
            self._finalize("connection-failed")
            return

        self._websocket.set_keepalive_interval(5)
        self._websocket.set_max_incoming_payload_size(1048576)
        self._websocket.connect("message", self._on_websocket_message)
        self._websocket.connect("closed", self._on_websocket_closed)
        self._websocket.connect("closing", self._on_websocket_closing)
        self._websocket.connect("error", self._on_websocket_error)
        self._websocket.connect("pong", self._on_websocket_pong)

        self.state = TCPState.CONNECTED
        self.notify("connected")

    def start_tls_negotiation(self) -> None:
        # Soup.Session does this automatically
        raise NotImplementedError

    def _check_certificate(
        self,
        _message: Soup.Message,
        certificate: Gio.TlsCertificate,
        errors: Gio.TlsCertificateFlags,
    ) -> bool:

        self._peer_certificate = certificate
        self._peer_certificate_errors = convert_tls_error_flags(errors)

        if self._accept_certificate():
            return True

        self.notify("bad-certificate")
        self._cancellable.cancel()
        return False

    def _on_network_event(
        self,
        _message: Soup.Message,
        event: Gio.SocketClientEvent,
        connection: Gio.TlsConnection,
    ) -> None:

        if event == Gio.SocketClientEvent.TLS_HANDSHAKED:
            self._tls_con = connection

    def _on_certificate_set(self, message: Soup.Message, _param: Any) -> None:
        if self._peer_certificate is not None:
            return

        # If the cert has errors _check_certificate() will set the cert.
        self._peer_certificate = message.props.tls_peer_certificate
        self._peer_certificate_errors = convert_tls_error_flags(
            message.props.tls_peer_certificate_errors
        )

    def _on_websocket_message(
        self, _websocket: Soup.WebsocketConnection, _type: int, message: GLib.Bytes
    ) -> None:
        data = message.get_data().decode()
        self._log_stanza(data)

        if self._input_closed:
            self._log.warning("Received data after stream closed")
            return

        self.notify("data-received", data)

    def _on_websocket_pong(
        self, _websocket: Soup.WebsocketConnection, _message: GLib.Bytes
    ) -> None:
        self._log.info("Pong received")

    def _on_websocket_closed(self, websocket: Soup.WebsocketConnection) -> None:
        self._log.info("Closed %s", get_websocket_close_string(websocket))
        self._finalize("disconnected")

    def _on_websocket_closing(self, _websocket: Soup.WebsocketConnection) -> None:
        self._log.info("Closing")

    def _on_websocket_error(
        self, _websocket: Soup.WebsocketConnection, error: GLib.Error
    ) -> None:
        self._log.error(error)
        if self._state not in (TCPState.DISCONNECTED, TCPState.DISCONNECTING):
            self._finalize("disconnected")

    def send(self, stanza: Protocol, now: bool = False) -> None:
        if self._state in (TCPState.DISCONNECTED, TCPState.DISCONNECTING):
            self._log.warning("send() not possible in state: %s", self._state)
            return

        data = str(stanza)
        self._websocket.send_text(data)
        self._log_stanza(data, received=False)
        self.notify("data-sent", stanza)

    def disconnect(self) -> None:
        if self._state == TCPState.CONNECTING:
            self.state = TCPState.DISCONNECTING
            self._cancellable.cancel()
            return

        if self._state in (TCPState.DISCONNECTED, TCPState.DISCONNECTING):
            self._log.warning("Called disconnect on state: %s", self._state)
            return

        self._websocket.close(Soup.WebsocketCloseCode.NORMAL, None)
        self.state = TCPState.DISCONNECTING

    def _check_for_shutdown(self) -> None:
        if self._input_closed and self._output_closed:
            self._websocket.close(Soup.WebsocketCloseCode.NORMAL, None)

    def shutdown_input(self) -> None:
        self._log.info("Shutdown input")
        self._input_closed = True
        self._check_for_shutdown()

    def shutdown_output(self) -> None:
        self.state = TCPState.DISCONNECTING
        self._log.info("Shutdown output")
        self._output_closed = True

    def _finalize(self, signal_name: str) -> None:
        self._input_closed = True
        self._output_closed = True
        self.state = TCPState.DISCONNECTED
        self.notify(signal_name)
        self.destroy()

    def destroy(self) -> None:
        super().destroy()
        self._session.abort()
        self._session = None
        self._websocket = None
