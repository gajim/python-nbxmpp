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

from typing import Optional

import logging

from gi.repository import Gio

from nbxmpp.const import TCPState
from nbxmpp.util import Observable
from nbxmpp.util import LogAdapter

log = logging.getLogger('nbxmpp.connection')


class Connection(Observable):
    '''
    Base Connection Class

    Signals:

        data-sent
        data-received
        bad-certificate
        certificate-set
        connection-failed
        disconnected
    '''
    def __init__(self,
                 log_context,
                 address,
                 accepted_certificates,
                 ignore_tls_errors,
                 ignored_tls_errors,
                 client_cert):

        self._log = LogAdapter(log, {'context': log_context})

        Observable.__init__(self, self._log)

        self._client_cert = client_cert
        self._address = address
        self._local_address = None
        self._remote_address = None
        self._state = None

        self._state = TCPState.DISCONNECTED

        self._peer_certificate = None
        self._peer_certificate_errors = None
        self._accepted_certificates = accepted_certificates
        self._ignore_tls_errors = ignore_tls_errors
        self._ignored_tls_errors = ignored_tls_errors

    @property
    def tls_version(self) -> Optional[int]:
        return None

    @property
    def ciphersuite(self) -> Optional[int]:
        return None

    @property
    def local_address(self):
        return self._local_address

    @property
    def remote_address(self):
        return self._remote_address

    @property
    def peer_certificate(self):
        return (self._peer_certificate, self._peer_certificate_errors)

    @property
    def connection_type(self):
        return self._address.type

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self._log.info('Set Connection State: %s', value)
        self._state = value

    def _accept_certificate(self):
        if not self._peer_certificate_errors:
            return True

        self._log.info('Found TLS certificate errors: %s',
                       self._peer_certificate_errors)

        if self._ignore_tls_errors:
            self._log.warning('Ignore all errors')
            return True

        if self._ignored_tls_errors:
            self._log.warning('Ignore TLS certificate errors: %s',
                              self._ignored_tls_errors)
            self._peer_certificate_errors -= self._ignored_tls_errors

        if Gio.TlsCertificateFlags.UNKNOWN_CA in self._peer_certificate_errors:
            for accepted_certificate in self._accepted_certificates:
                if self._peer_certificate.is_same(accepted_certificate):
                    self._peer_certificate_errors.discard(
                        Gio.TlsCertificateFlags.UNKNOWN_CA)
                    break

        if not self._peer_certificate_errors:
            return True
        return False

    def disconnect(self):
        raise NotImplementedError

    def connect(self):
        raise NotImplementedError

    def send(self, stanza, now=False):
        raise NotImplementedError

    def _log_stanza(self, data, received=True):
        direction = 'RECEIVED' if received else 'SENT'
        message = ('::::: DATA %s ::::\n\n%s\n')
        self._log.info(message, direction, data)

    def start_tls_negotiation(self):
        raise NotImplementedError

    def shutdown_output(self):
        raise NotImplementedError

    def shutdown_input(self):
        raise NotImplementedError

    def destroy(self):
        self.remove_subscriptions()
        self._peer_certificate = None
        self._client_cert = None
        self._address = None
