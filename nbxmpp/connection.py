# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

import logging

from gi.repository import Gio

from nbxmpp.const import ConnectionType
from nbxmpp.const import TCPState
from nbxmpp.structs import ServerAddress
from nbxmpp.util import LogAdapter
from nbxmpp.util import min_version
from nbxmpp.util import Observable

log = logging.getLogger("nbxmpp.connection")


class Connection(Observable):
    """
    Base Connection Class

    Signals:

        data-sent
        data-received
        bad-certificate
        connection-failed
        disconnected
    """

    def __init__(
        self,
        log_context: str | None,
        address: ServerAddress,
        accepted_certificates: list[Gio.TlsCertificate],
        ignore_tls_errors: bool,
        ignored_tls_errors: set[Gio.TlsCertificateFlags],
        client_cert: Any,
    ) -> None:

        self._log = LogAdapter(log, {"context": log_context})

        Observable.__init__(self, self._log)

        self._client_cert = client_cert
        self._address = address
        self._local_address: Gio.SocketAddress | None = None
        self._remote_address: str | None = None

        self._state = TCPState.DISCONNECTED
        self._tls_con: Gio.TlsConnection | None = None

        self._peer_certificate: Gio.TlsCertificate | None = None
        self._peer_certificate_errors: set[Gio.TlsCertificateFlags] | None = None
        self._accepted_certificates = accepted_certificates
        self._ignore_tls_errors = ignore_tls_errors
        self._ignored_tls_errors = ignored_tls_errors

    @property
    def tls_version(self) -> int | None:
        if self._tls_con is None:
            return None

        if not min_version("GLib", "2.69.0"):
            return None

        return self._tls_con.get_protocol_version()

    @property
    def ciphersuite(self) -> str | None:
        if self._tls_con is None:
            return None

        if not min_version("GLib", "2.69.0"):
            return None

        return self._tls_con.get_ciphersuite_name()

    def get_channel_binding_data(
        self, type_: Gio.TlsChannelBindingType
    ) -> bytes | None:
        assert self._tls_con is not None

        try:
            success, data = self._tls_con.get_channel_binding_data(type_)
        except Exception as error:
            self._log.warning("Unable to get channel binding data: %s", error)
            return None

        if not success:
            return None
        return data

    @property
    def local_address(self) -> Gio.SocketAddress | None:
        return self._local_address

    @property
    def remote_address(self) -> str | None:
        return self._remote_address

    @property
    def peer_certificate(
        self,
    ) -> tuple[Gio.TlsCertificate | None, set[Gio.TlsCertificateFlags] | None]:
        return (self._peer_certificate, self._peer_certificate_errors)

    @property
    def connection_type(self) -> ConnectionType:
        assert self._address is not None
        return self._address.type

    @property
    def state(self) -> TCPState:
        return self._state

    @state.setter
    def state(self, value: TCPState) -> None:
        self._log.info("Set Connection State: %s", value)
        self._state = value

    def _accept_certificate(self) -> bool:
        if not self._peer_certificate_errors:
            return True

        self._log.info(
            "Found TLS certificate errors: %s", self._peer_certificate_errors
        )

        if self._ignore_tls_errors:
            self._log.warning("Ignore all errors")
            return True

        if self._ignored_tls_errors:
            self._log.warning(
                "Ignore TLS certificate errors: %s", self._ignored_tls_errors
            )
            self._peer_certificate_errors -= self._ignored_tls_errors

        if Gio.TlsCertificateFlags.UNKNOWN_CA in self._peer_certificate_errors:
            for accepted_certificate in self._accepted_certificates:
                assert self._peer_certificate is not None
                if self._peer_certificate.is_same(accepted_certificate):
                    self._peer_certificate_errors.discard(
                        Gio.TlsCertificateFlags.UNKNOWN_CA
                    )
                    break

        return bool(not self._peer_certificate_errors)

    def disconnect(self) -> None:
        raise NotImplementedError

    def connect(self) -> None:
        raise NotImplementedError

    def send(self, stanza: Any, now: bool = False) -> None:
        raise NotImplementedError

    def _log_stanza(self, data: str, received: bool = True) -> None:
        direction = "RECEIVED" if received else "SENT"
        message = "::::: DATA %s ::::\n\n%s\n"
        self._log.info(message, direction, data)

    def start_tls_negotiation(self) -> None:
        raise NotImplementedError

    def shutdown_output(self) -> None:
        raise NotImplementedError

    def shutdown_input(self) -> None:
        raise NotImplementedError

    def destroy(self) -> None:
        self.remove_subscriptions()
        self._peer_certificate = None
        self._client_cert = None
        self._address = None
        self._tls_con = None
