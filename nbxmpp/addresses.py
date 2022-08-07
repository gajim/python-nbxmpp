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

import logging
from collections import namedtuple

from gi.repository import Soup

import nbxmpp
from nbxmpp.util import Observable
from nbxmpp.const import ConnectionType
from nbxmpp.const import ConnectionProtocol
from nbxmpp.util import parse_websocket_uri


log = logging.getLogger('nbxmpp.addresses')


class ServerAddress(namedtuple('ServerAddress', 'domain service host uri '
                                                'protocol type proxy')):

    __slots__ = []

    @property
    def is_service(self):
        return self.service is not None

    @property
    def is_host(self):
        return self.host is not None

    @property
    def is_uri(self):
        return self.uri is not None

    def has_proxy(self):
        return self.proxy is not None


class ServerAddresses(Observable):
    '''
    Signals:

        resolved

    '''

    def __init__(self, domain):
        Observable.__init__(self, log)

        self._domain = domain
        self._custom_host = None
        self._proxy = None
        self._is_resolved = False

        self._addresses = [
            ServerAddress(domain=self._domain,
                          service='xmpps-client',
                          host=None,
                          uri=None,
                          protocol=ConnectionProtocol.TCP,
                          type=ConnectionType.DIRECT_TLS,
                          proxy=None),

            ServerAddress(domain=self._domain,
                          service='xmpp-client',
                          host=None,
                          uri=None,
                          protocol=ConnectionProtocol.TCP,
                          type=ConnectionType.START_TLS,
                          proxy=None),

            ServerAddress(domain=self._domain,
                          service='xmpp-client',
                          host=None,
                          uri=None,
                          protocol=ConnectionProtocol.TCP,
                          type=ConnectionType.PLAIN,
                          proxy=None)
        ]

        self._fallback_addresses = [
            ServerAddress(domain=self._domain,
                          service=None,
                          host='%s:%s' % (self._domain, 5222),
                          uri=None,
                          protocol=ConnectionProtocol.TCP,
                          type=ConnectionType.START_TLS,
                          proxy=None),

            ServerAddress(domain=self._domain,
                          service=None,
                          host='%s:%s' % (self._domain, 5222),
                          uri=None,
                          protocol=ConnectionProtocol.TCP,
                          type=ConnectionType.PLAIN,
                          proxy=None)
        ]

    @property
    def domain(self):
        return self._domain

    @property
    def is_resolved(self):
        return self._is_resolved

    def resolve(self):
        if self._is_resolved:
            self._on_request_resolved()
            return

        if self._proxy is not None:
            # Let the proxy resolve the domain
            self._on_request_resolved()
            return

        if self._custom_host is not None:
            self._on_request_resolved()
            return

        self._resolve_alternatives()

    def _resolve_alternatives(self) -> None:
        session = Soup.Session()
        session.props.timeout = 5
        session.props.user_agent = f'nbxmpp/{nbxmpp.__version__}'
        message = Soup.Message.new(
            'GET', f'https://{self._domain}/.well-known/host-meta')
        session.queue_message(message, self._on_alternatives_result)

    def _on_alternatives_result(self,
                                _session: Soup.Session,
                                message: Soup.Message) -> None:

        status = message.props.status_code
        if status != Soup.Status.OK:
            error = message.props.reason_phrase
            log.info('Failed to retrieve host-meta file: %s %s', status, error)
            self._on_request_resolved()
            return

        response_body = message.props.response_body
        if response_body is None or not response_body.data:
            log.info('No response body data found')
            self._on_request_resolved()
            return

        try:
            uri = parse_websocket_uri(response_body.data)
        except Exception as error:
            log.info('Error parsing websocket uri: %s', error)
            self._on_request_resolved()
            return

        if uri.startswith('wss'):
            type_ = ConnectionType.DIRECT_TLS
        elif uri.startswith('ws'):
            type_ = ConnectionType.PLAIN
        else:
            log.warning('Invalid websocket uri: %s', uri)
            self._on_request_resolved()
            return

        addr = ServerAddress(domain=self._domain,
                             service=None,
                             host=None,
                             uri=uri,
                             protocol=ConnectionProtocol.WEBSOCKET,
                             type=type_,
                             proxy=None)
        self._addresses.append(addr)

        self._on_request_resolved()

    def cancel_resolve(self):
        self.remove_subscriptions()

    def set_custom_host(self, address):
        # Set a custom host, overwrites all other addresses
        self._custom_host = address
        if address is None:
            return

        host_or_uri, protocol, type_ = address
        if protocol == ConnectionProtocol.WEBSOCKET:
            host, uri = None, host_or_uri
        else:
            host, uri = host_or_uri, None

        self._fallback_addresses = []
        self._addresses = [
            ServerAddress(domain=self._domain,
                          service=None,
                          host=host,
                          uri=uri,
                          protocol=protocol,
                          type=type_,
                          proxy=None)]

    def set_proxy(self, proxy):
        self._proxy = proxy

    def _on_request_resolved(self):
        self._is_resolved = True
        self.notify('resolved')
        self.remove_subscriptions()

    def get_next_address(self,
                         allowed_types,
                         allowed_protocols):
        '''
        Selects next address
        '''

        for addr in self._filter_allowed(self._addresses,
                                         allowed_types,
                                         allowed_protocols):
            yield self._assure_proxy(addr)

        for addr in self._filter_allowed(self._fallback_addresses,
                                         allowed_types,
                                         allowed_protocols):
            yield self._assure_proxy(addr)

        raise NoMoreAddresses

    def _assure_proxy(self, addr):
        if self._proxy is None:
            return addr

        if addr.protocol == ConnectionProtocol.TCP:
            return addr._replace(proxy=self._proxy)

        return addr

    def _filter_allowed(self, addresses, allowed_types, allowed_protocols):
        if self._proxy is not None:
            addresses = filter(lambda addr: addr.host is not None, addresses)

        addresses = filter(lambda addr: addr.type in allowed_types,
                           addresses)
        addresses = filter(lambda addr: addr.protocol in allowed_protocols,
                           addresses)
        return addresses

    def __str__(self):
        addresses = self._addresses + self._fallback_addresses
        return '\n'.join([str(addr) for addr in addresses])


class NoMoreAddresses(Exception):
    pass
