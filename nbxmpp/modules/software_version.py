# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from collections.abc import Callable

from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import ERR_FORBIDDEN
from nbxmpp.protocol import ERR_SERVICE_UNAVAILABLE
from nbxmpp.protocol import Error
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import IqProperties
from nbxmpp.structs import SoftwareVersionResult
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client


class SoftwareVersion(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="iq",
                callback=self._answer_request,
                typ="get",
                priority=60,
                ns=Namespace.VERSION,
            ),
        ]

        self._name: str | None = None
        self._version: str | None = None
        self._os: str | None = None

        self._enabled = False
        self._allow_reply_func: Callable[..., bool] | None = None

    def disable(self) -> None:
        self._enabled = False

    def set_allow_reply_func(self, func: Callable[..., bool]) -> None:
        self._allow_reply_func = func

    @iq_request_task
    def request_software_version(self, jid: JID):
        _task = yield

        response = yield Iq(typ="get", to=jid, queryNS=Namespace.VERSION)
        if response.isError():
            raise StanzaError(response)

        yield _parse_info(response)

    def set_software_version(
        self, name: str, version: str, os: str | None = None
    ) -> None:
        self._name, self._version, self._os = name, version, os
        self._enabled = True

    def _answer_request(
        self, _client: Client, stanza: Iq, _properties: IqProperties
    ) -> None:
        self._log.info("Request received from %s", stanza.getFrom())
        if not self._enabled or self._name is None or self._version is None:
            self._client.send_stanza(Error(stanza, ERR_SERVICE_UNAVAILABLE))
            raise NodeProcessed

        if self._allow_reply_func is not None:
            if not self._allow_reply_func(stanza.getFrom()):
                self._client.send_stanza(Error(stanza, ERR_FORBIDDEN))
                raise NodeProcessed

        iq = stanza.buildReply("result")
        query = iq.getQuery()
        query.setTagData("name", self._name)
        query.setTagData("version", self._version)
        if self._os is not None:
            query.setTagData("os", self._os)
        self._log.info(
            "Send software version: %s %s %s", self._name, self._version, self._os
        )

        self._client.send_stanza(iq)
        raise NodeProcessed


def _parse_info(stanza: Iq) -> SoftwareVersionResult:
    try:
        name = stanza.getQueryChild("name").getData()
    except Exception:
        raise MalformedStanzaError("name node missing", stanza)

    try:
        version = stanza.getQueryChild("version").getData()
    except Exception:
        raise MalformedStanzaError("version node missing", stanza)

    os_info = stanza.getQueryChild("os")
    if os_info is not None:
        os_info = os_info.getData()

    return SoftwareVersionResult(name, version, os_info)
