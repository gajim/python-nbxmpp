# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from collections.abc import Iterator

from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import ConnectionType
from nbxmpp.http import HTTPRequest
from nbxmpp.http import HTTPSession
from nbxmpp.structs import ProxyData
from nbxmpp.structs import ServerAddress
from nbxmpp.types import CustomHostT
from nbxmpp.util import Observable
from nbxmpp.util import parse_websocket_uri

log = logging.getLogger("nbxmpp.addresses")


class ServerAddresses(Observable):
    """
    Signals:

        resolved

    """

    def __init__(self, domain: str | None) -> None:
        Observable.__init__(self, log)

        self._domain = domain
        self._http_session: HTTPSession | None = None
        self._custom_host: CustomHostT | None = None
        self._proxy: ProxyData | None = None
        self._is_resolved = False

        self._addresses: list[ServerAddress] = [
            ServerAddress(
                domain=self._domain,
                service="xmpps-client",
                host=None,
                uri=None,
                protocol=ConnectionProtocol.TCP,
                type=ConnectionType.DIRECT_TLS,
                proxy=None,
            ),
            ServerAddress(
                domain=self._domain,
                service="xmpp-client",
                host=None,
                uri=None,
                protocol=ConnectionProtocol.TCP,
                type=ConnectionType.START_TLS,
                proxy=None,
            ),
            ServerAddress(
                domain=self._domain,
                service="xmpp-client",
                host=None,
                uri=None,
                protocol=ConnectionProtocol.TCP,
                type=ConnectionType.PLAIN,
                proxy=None,
            ),
        ]

        self._fallback_addresses: list[ServerAddress] = [
            ServerAddress(
                domain=self._domain,
                service=None,
                host="%s:%s" % (self._domain, 5222),
                uri=None,
                protocol=ConnectionProtocol.TCP,
                type=ConnectionType.START_TLS,
                proxy=None,
            ),
            ServerAddress(
                domain=self._domain,
                service=None,
                host="%s:%s" % (self._domain, 5222),
                uri=None,
                protocol=ConnectionProtocol.TCP,
                type=ConnectionType.PLAIN,
                proxy=None,
            ),
        ]

    @property
    def domain(self) -> str | None:
        return self._domain

    @property
    def is_resolved(self) -> bool:
        return self._is_resolved

    def resolve(self) -> None:
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
        if self._http_session is None:
            self._on_request_resolved()
            return

        request = self._http_session.create_request()
        request.send(
            "GET",
            f"https://{self._domain}/.well-known/host-meta",
            timeout=5,
            callback=self._on_alternatives_result,
        )

    def _on_alternatives_result(self, request: HTTPRequest) -> None:
        if not request.is_complete():
            log.info(
                "Failed to retrieve host-meta file: %s", request.get_error_string()
            )
            self._on_request_resolved()
            return

        response_body = request.get_data()
        if not response_body:
            log.info("No response body data found")
            self._on_request_resolved()
            return

        try:
            uri = parse_websocket_uri(response_body.decode())
        except Exception as error:
            log.info("Error parsing websocket uri: %s", error)
            self._on_request_resolved()
            return

        if uri.startswith("wss"):
            type_ = ConnectionType.DIRECT_TLS
        elif uri.startswith("ws"):
            type_ = ConnectionType.PLAIN
        else:
            log.warning("Invalid websocket uri: %s", uri)
            self._on_request_resolved()
            return

        addr = ServerAddress(
            domain=self._domain,
            service=None,
            host=None,
            uri=uri,
            protocol=ConnectionProtocol.WEBSOCKET,
            type=type_,
            proxy=None,
        )
        self._addresses.append(addr)

        self._on_request_resolved()

    def cancel_resolve(self) -> None:
        self.remove_subscriptions()

    def set_custom_host(self, address: CustomHostT | None) -> None:
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
            ServerAddress(
                domain=self._domain,
                service=None,
                host=host,
                uri=uri,
                protocol=protocol,
                type=type_,
                proxy=None,
            )
        ]

    def set_proxy(self, proxy: ProxyData | None) -> None:
        self._proxy = proxy

    def set_http_session(self, session: HTTPSession) -> None:
        self._http_session = session

    def _on_request_resolved(self) -> None:
        self._is_resolved = True
        self.notify("resolved")
        self.remove_subscriptions()

    def get_next_address(
        self,
        allowed_types: list[ConnectionType],
        allowed_protocols: list[ConnectionProtocol],
    ) -> Iterator[ServerAddress]:
        """
        Selects next address
        """

        for addr in self._filter_allowed(
            self._addresses, allowed_types, allowed_protocols
        ):
            yield self._assure_proxy(addr)

        for addr in self._filter_allowed(
            self._fallback_addresses, allowed_types, allowed_protocols
        ):
            yield self._assure_proxy(addr)

        raise NoMoreAddresses

    def _assure_proxy(self, addr: ServerAddress) -> ServerAddress:
        if self._proxy is None:
            return addr

        if addr.protocol == ConnectionProtocol.TCP:
            return addr._replace(proxy=self._proxy)

        return addr

    def _filter_allowed(
        self,
        addresses: list[ServerAddress],
        allowed_types: list[ConnectionType],
        allowed_protocols: list[ConnectionProtocol],
    ) -> Iterator[ServerAddress]:
        if self._proxy is not None:
            addresses = filter(lambda addr: addr.host is not None, addresses)

        addresses = filter(lambda addr: addr.type in allowed_types, addresses)
        addresses = filter(lambda addr: addr.protocol in allowed_protocols, addresses)
        return addresses

    def __str__(self) -> str:
        addresses = self._addresses + self._fallback_addresses
        return "\n".join([str(addr) for addr in addresses])


class NoMoreAddresses(Exception):
    pass
