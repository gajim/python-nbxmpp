# Copyright (C) 2021 Philipp Hörist <philipp AT hoerist.com>
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
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import IqProperties
from nbxmpp.structs import LastActivityData
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client


class LastActivity(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="iq",
                callback=self._answer_request,
                priority=60,
                typ="get",
                ns=Namespace.LAST,
            ),
        ]

        self._idle_func: Callable[..., int] | None = None
        self._allow_reply_func: Callable[..., bool] | None = None

    def disable(self) -> None:
        self._idle_func = None

    def set_idle_func(self, func: Callable[..., int]) -> None:
        self._idle_func = func

    def set_allow_reply_func(self, func: Callable[..., bool]) -> None:
        self._allow_reply_func = func

    @iq_request_task
    def request_last_activity(self, jid: str):
        _task = yield

        response = yield _make_request(jid)
        if response.isError():
            raise StanzaError(response)

        yield _parse_response(response)

    def _answer_request(
        self, _client: Client, stanza: Iq, _properties: IqProperties
    ) -> None:
        self._log.info("Request received from %s", stanza.getFrom())
        if self._idle_func is None:
            self._client.send_stanza(Error(stanza, ERR_SERVICE_UNAVAILABLE))
            raise NodeProcessed

        if self._allow_reply_func is not None:
            if not self._allow_reply_func(stanza.getFrom()):
                self._client.send_stanza(Error(stanza, ERR_FORBIDDEN))
                raise NodeProcessed

        seconds = self._idle_func()
        iq = stanza.buildReply("result")
        query = iq.getQuery()
        query.setAttr("seconds", seconds)
        self._log.info("Send last activity: %s", seconds)
        self._client.send_stanza(iq)
        raise NodeProcessed


def _make_request(jid: str) -> Iq:
    return Iq("get", queryNS=Namespace.LAST, to=jid)


def _parse_response(response: Iq) -> LastActivityData:
    query = response.getQuery()
    seconds = query.getAttr("seconds")

    try:
        seconds = int(seconds)
    except Exception:
        raise MalformedStanzaError("seconds attribute invalid", response)

    return LastActivityData(seconds=seconds, status=query.getData())
