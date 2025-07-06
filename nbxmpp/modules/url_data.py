# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

# XEP-0103 / XEP-0104

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from nbxmpp.namespaces import Namespace
from nbxmpp.simplexml import Node
from nbxmpp.util import from_xs_boolean


@dataclass
class HTTPUrlSchemeAuth:
    scheme: str
    params: list[tuple[str, str | None]]

    @classmethod
    def from_node(cls, auth: Node) -> HTTPUrlSchemeAuth:
        scheme = auth.getAttr("scheme")
        if not scheme:
            raise ValueError("missing scheme attribute")

        params: list[tuple[str, str | None]] = []
        for param in auth.getTags(
            "auth-param", namespace=Namespace.URL_DATA_HTTP_SCHEME
        ):
            name = param.getAttr("name")
            if not name:
                raise ValueError("missing name attribute")

            value = param.getAttr("value") or None
            params.append((name, value))

        return cls(scheme=scheme, params=params)

    def get_param(self, param_name: str) -> str | None:
        for name, value in self.params:
            if name == param_name:
                return value
        return None


@dataclass
class HTTPUrlSchemeCookie:
    name: str
    value: str | None
    comment: str | None
    domain: str | None
    path: str | None
    max_age: int = 0
    secure: bool = False
    version: str = "1.0"

    @classmethod
    def from_node(cls, cookie: Node) -> HTTPUrlSchemeCookie:
        name = cookie.getAttr("name")
        if not name:
            raise ValueError("missing name attribute")

        value = cookie.getAttr("value") or None
        comment = cookie.getAttr("comment") or None
        domain = cookie.getAttr("domain") or None
        path = cookie.getAttr("path") or None

        try:
            max_age = int(cookie.getAttr("max-age") or "")
        except Exception:
            max_age = 0

        if max_age < 0:
            raise ValueError("invalid max-age: %s" % max_age)

        try:
            secure = from_xs_boolean(cookie.getAttr("secure") or "false")
        except Exception:
            raise ValueError("unable to parse secure attribute")

        version = cookie.getAttr("version") or "1.0"

        return cls(
            name=name,
            value=value,
            comment=comment,
            domain=domain,
            path=path,
            max_age=max_age,
            secure=secure,
            version=version,
        )


@dataclass
class HTTPUrlSchemeData:
    auth: HTTPUrlSchemeAuth | None = None
    cookie: HTTPUrlSchemeCookie | None = None
    headers: list[tuple[str, str]] = field(default_factory=list)

    @classmethod
    def from_node(cls, url_data: Node) -> HTTPUrlSchemeData:
        auth = url_data.getTag("auth", namespace=Namespace.URL_DATA_HTTP_SCHEME)
        if auth is not None:
            auth = HTTPUrlSchemeAuth.from_node(auth)

        cookie = url_data.getTag("cookie", namespace=Namespace.URL_DATA_HTTP_SCHEME)
        if cookie is not None:
            cookie = HTTPUrlSchemeCookie.from_node(cookie)

        headers: list[tuple[str, str]] = []
        for header in url_data.getTags(
            "header", namespace=Namespace.URL_DATA_HTTP_SCHEME
        ):
            name = header.getAttr("name")
            if not name:
                raise ValueError("missing name attribute")

            value = header.getAttr("value") or ""
            headers.append((name, value))

        return cls(auth=auth, cookie=cookie, headers=headers)


@dataclass
class UrlData:

    target: str
    sid: str | None
    scheme_data: dict[str, HTTPUrlSchemeData]

    @classmethod
    def from_node(cls, url_data: Node) -> UrlData:
        target = url_data.getAttr("target")
        if not target:
            raise ValueError("missing target attribute")

        sid = url_data.getAttr("sid") or None

        scheme_data: dict[str, HTTPUrlSchemeData] = {}
        if url_data.getAttr("xmlns:http") == Namespace.URL_DATA_HTTP_SCHEME:
            scheme_data[Namespace.URL_DATA_HTTP_SCHEME] = HTTPUrlSchemeData.from_node(
                url_data
            )

        return cls(sid=sid, target=target, scheme_data=scheme_data)
