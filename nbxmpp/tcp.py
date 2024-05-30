# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

import logging
from collections import deque

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject

from nbxmpp.connection import Connection
from nbxmpp.const import ConnectionType
from nbxmpp.const import TCPState
from nbxmpp.protocol import Protocol
from nbxmpp.util import convert_tls_error_flags
from nbxmpp.util import utf8_decode

log = logging.getLogger("nbxmpp.tcp")

READ_BUFFER_SIZE = 8192


class TCPConnection(Connection):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        Connection.__init__(self, *args, **kwargs)

        self._client = Gio.SocketClient.new()
        self._client.set_protocol(Gio.SocketProtocol.TCP)
        self._client.set_timeout(7)

        if self._address.proxy is not None:
            self._proxy_resolver = self._address.proxy.get_resolver()
            self._client.set_proxy_resolver(self._proxy_resolver)

        GObject.Object.connect(self._client, "event", self._on_event)

        self._con: Gio.SocketConnection | None = None

        self._read_buffer = b""

        self._write_queue: deque[Protocol] | None = deque([])
        self._write_stanza_buffer: deque[Protocol] | None = None

        self._connect_cancellable = Gio.Cancellable()
        self._read_cancellable = Gio.Cancellable()

        self._tls_handshake_in_progress = False
        self._input_closed = False
        self._output_closed = False

        self._keepalive_id: int | None = None

    def connect(self) -> None:
        self.state = TCPState.CONNECTING

        if self._address.is_service:
            self._client.connect_to_service_async(
                self._address.domain,
                self._address.service,
                self._connect_cancellable,
                self._on_connect_finished,
                None,
            )
        elif self._address.is_host:
            self._client.connect_to_host_async(
                self._address.host,
                0,
                self._connect_cancellable,
                self._on_connect_finished,
                None,
            )

        else:
            raise ValueError("Invalid Address")

    def _on_event(
        self,
        _socket_client: Gio.SocketClient,
        event: Gio.SocketClientEvent,
        _connectable: Gio.SocketConnectable,
        connection: Gio.SocketConnection,
    ) -> None:
        if event == Gio.SocketClientEvent.CONNECTING:
            self._remote_address = connection.get_remote_address().to_string()
            use_proxy = self._address.proxy is not None
            target = "proxy" if use_proxy else self._address.domain
            self._log.info("Connecting to %s (%s)", target, self._remote_address)

    def _check_certificate(
        self,
        _connection: Gio.TlsClientConnection,
        certificate: Gio.TlsCertificate,
        errors: Gio.TlsCertificateFlags,
    ) -> bool:
        self._peer_certificate = certificate
        self._peer_certificate_errors = convert_tls_error_flags(errors)

        if self._accept_certificate():
            return True

        self.notify("bad-certificate")
        return False

    def _on_certificate_set(
        self, connection: Gio.TlsClientConnection, _param: Any
    ) -> None:
        if self._peer_certificate is None:
            # If the cert has errors _check_certificate() will set the cert and
            # _accept_certificate() will modify the error set. If this is the
            # case _accept_certificate() modifies the errors.
            self._peer_certificate = connection.props.peer_certificate
            self._peer_certificate_errors = convert_tls_error_flags(
                connection.props.peer_certificate_errors
            )

        self._tls_handshake_in_progress = False

    def _on_connect_finished(
        self, client: Gio.SocketClient, result: Gio.AsyncResult, _user_data: Any
    ) -> None:
        try:
            if self._address.proxy is not None:
                self._con = client.connect_to_host_finish(result)
            elif self._address.is_service:
                self._con = client.connect_to_service_finish(result)
            elif self._address.is_host:
                self._con = client.connect_to_host_finish(result)
            else:
                raise ValueError("Address must be a service or host")
        except GLib.Error as error:
            self._log.info("Connect Error: %s", error)
            self._finalize("connection-failed")
            return

        # We use the timeout only for connecting
        self._con.get_socket().set_timeout(0)
        self._con.set_graceful_disconnect(True)
        self._con.get_socket().set_keepalive(True)

        self._local_address = self._con.get_local_address()

        self.state = TCPState.CONNECTED

        use_proxy = self._address.proxy is not None
        target = "proxy" if use_proxy else self._address.domain
        self._log.info(
            "Connected to %s (%s)", target, self._con.get_remote_address().to_string()
        )

        self._on_connected()

    def _on_connected(self) -> None:
        self.notify("connected")
        self._read_async()

    def _remove_keepalive_timer(self) -> None:
        if self._keepalive_id is not None:
            self._log.info("Remove keepalive timer")
            GLib.source_remove(self._keepalive_id)
            self._keepalive_id = None

    def _renew_keepalive_timer(self) -> None:
        if self._con is None:
            return
        self._remove_keepalive_timer()
        self._log.info("Add keepalive timer")
        self._keepalive_id = GLib.timeout_add_seconds(5, self._send_keepalive)

    def _send_keepalive(self) -> None:
        self._log.info("Send keepalive")
        self._keepalive_id = None
        if not self._con.get_output_stream().has_pending():
            self._write_all_async(b" ")

    def start_tls_negotiation(self) -> None:
        self._log.info("Start TLS negotiation")
        self._tls_handshake_in_progress = True
        remote_address = self._con.get_remote_address()
        identity = Gio.NetworkAddress.new(
            self._address.domain, remote_address.props.port
        )

        self._tls_con = Gio.TlsClientConnection.new(self._con, identity)

        if self._address.type == ConnectionType.DIRECT_TLS:
            self._tls_con.set_advertised_protocols(["xmpp-client"])
        self._tls_con.connect("accept-certificate", self._check_certificate)
        self._tls_con.connect("notify::peer-certificate", self._on_certificate_set)

        # This Wraps the Gio.TlsClientConnection and the Gio.Socket together
        # so we get back a Gio.SocketConnection
        self._con = Gio.TcpWrapperConnection.new(self._tls_con, self._con.get_socket())

    def _read_async(self) -> None:
        if self._input_closed:
            return

        self._con.get_input_stream().read_bytes_async(
            READ_BUFFER_SIZE,
            GLib.PRIORITY_LOW,
            self._read_cancellable,
            self._on_read_async_finish,
            None,
        )

    def _on_read_async_finish(
        self, stream: Gio.InputStream, result: Gio.AsyncResult, _user_data: Any
    ) -> None:
        try:
            data = stream.read_bytes_finish(result)
        except GLib.Error as error:
            quark = GLib.quark_try_string("g-io-error-quark")
            if error.matches(quark, Gio.IOErrorEnum.CANCELLED):
                if self._input_closed:
                    return

            quark = GLib.quark_try_string("g-tls-error-quark")
            if error.matches(quark, Gio.TlsError.MISC):
                if self._tls_handshake_in_progress:
                    self._log.error("Handshake failed: %s", error)
                    self._finalize("connection-failed")
                    return

            if error.matches(quark, Gio.TlsError.EOF):
                self._log.info("Incoming stream closed: TLS EOF")
                self._finalize("disconnected")
                return

            if error.matches(quark, Gio.TlsError.BAD_CERTIFICATE):
                self._log.info("Certificate Error: %s", error)
                self._finalize("disconnected")
                return

            self._log.error("Read Error: %s", error)

            if self._state not in (TCPState.DISCONNECTING, TCPState.DISCONNECTED):
                self._finalize("disconnected")
            return

        except RuntimeError as error:
            # PyGObject raises a RuntimeError when it fails to convert the
            # GError. Why it failed is printed by PyGObject
            self._log.error(error)
            return

        data = data.get_data()
        if not data:
            self._log.info("Reveived zero data on _read_async()")
            self._finalize("disconnected")
            return

        self._renew_keepalive_timer()

        self._read_buffer += data

        try:
            data, self._read_buffer = utf8_decode(self._read_buffer)
        except UnicodeDecodeError as error:
            self._log.warning(error)
            self._log.warning('read buffer: "%s"', self._read_buffer)
            self._log.warning('data: "%s"', data)
            self._finalize("disconnected")
            return

        self._log_stanza(data, received=True)

        try:
            self.notify("data-received", data)
        except Exception:
            self._log.exception("Error while executing data-received:")

        # Call next async read only after the received data is processed
        # otherwise this can lead to problems if we call
        # start_tls_negotiation() while we have a pending read which is
        # the case for START TLS because its triggered by <proceed>
        self._read_async()

    def _write_stanzas(self) -> None:
        self._write_stanza_buffer = self._write_queue
        self._write_queue = deque([])
        data = "".join(map(str, self._write_stanza_buffer)).encode()
        self._write_all_async(data)

    def _write_all_async(self, data: bytes) -> None:
        # We have to pass data to the callback, because GLib takes no
        # reference on the passed data and python would gc collect it
        # bevor GLib has a chance to write it to the stream
        self._con.get_output_stream().write_all_async(
            data, GLib.PRIORITY_DEFAULT, None, self._on_write_all_async_finished, data
        )

    def _on_write_all_async_finished(
        self, stream: Gio.OutputStream, result: Gio.AsyncResult, data: bytes
    ) -> None:
        try:
            stream.write_all_finish(result)
        except GLib.Error as error:
            quark = GLib.quark_try_string("g-tls-error-quark")
            if error.matches(quark, Gio.TlsError.BAD_CERTIFICATE):
                self._write_stanza_buffer = None
                return

            if self._output_closed:
                self._check_for_shutdown()
                return

            self._log.error("Write Error: %s", error)
            return

        except RuntimeError as error:
            # PyGObject raises a RuntimeError when it fails to convert the
            # GError. Why it failed is printed by PyGObject
            self._log.error(error)
            return

        decoded_data = data.decode()
        self._log_stanza(decoded_data, received=False)

        if decoded_data == " ":
            # keepalive whitespace
            self._renew_keepalive_timer()

        else:
            for stanza in self._write_stanza_buffer:
                try:
                    self.notify("data-sent", stanza)
                except Exception:
                    self._log.exception("Error while executing data-sent:")

        if self._output_closed and not self._write_queue:
            self._check_for_shutdown()
            return

        if self._write_queue:
            self._write_stanzas()

    def send(self, stanza: Protocol, now: bool = False) -> None:
        if self._state in (TCPState.DISCONNECTED, TCPState.DISCONNECTING):
            self._log.warning("send() not possible in state: %s", self._state)
            return

        if now:
            self._write_queue.appendleft(stanza)
        else:
            self._write_queue.append(stanza)

        if not self._con.get_output_stream().has_pending():
            self._write_stanzas()

    def disconnect(self) -> None:
        self._remove_keepalive_timer()
        if self.state == TCPState.CONNECTING:
            self.state = TCPState.DISCONNECTING
            self._connect_cancellable.cancel()
            return

        if self._state in (TCPState.DISCONNECTED, TCPState.DISCONNECTING):
            self._log.warning("Called disconnect on state: %s", self._state)
            return

        self.state = TCPState.DISCONNECTING
        self._finalize("disconnected")

    def _check_for_shutdown(self) -> None:
        if self._input_closed and self._output_closed:
            self._finalize("disconnected")

    def shutdown_input(self) -> None:
        self._remove_keepalive_timer()
        self._log.info("Shutdown input")
        self._input_closed = True
        self._read_cancellable.cancel()
        self._check_for_shutdown()

    def shutdown_output(self) -> None:
        self._remove_keepalive_timer()
        self.state = TCPState.DISCONNECTING
        self._log.info("Shutdown output")
        self._output_closed = True

    def _finalize(self, signal_name: str) -> None:
        self._remove_keepalive_timer()
        if self._con is not None:
            try:
                self._con.get_socket().shutdown(True, True)
            except GLib.Error as error:
                self._log.info(error)
        self._input_closed = True
        self._output_closed = True
        self.state = TCPState.DISCONNECTED
        self.notify(signal_name)
        self.destroy()

    def destroy(self) -> None:
        super().destroy()
        self._con = None
        self._client = None
        self._write_queue = None
