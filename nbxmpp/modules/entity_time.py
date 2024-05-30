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
from nbxmpp.modules.date_and_time import create_tzinfo
from nbxmpp.modules.date_and_time import get_local_time
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import ERR_FORBIDDEN
from nbxmpp.protocol import ERR_SERVICE_UNAVAILABLE
from nbxmpp.protocol import Error
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import IqProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client


class EntityTime(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="iq",
                callback=self._answer_request,
                priority=60,
                typ="get",
                ns=Namespace.TIME,
            ),
        ]

        self._enabled = False
        self._allow_reply_func: Callable[..., bool] | None = None

    def disable(self) -> None:
        self._enabled = False

    def enable(self) -> None:
        self._enabled = True

    def set_allow_reply_func(self, func: Callable[..., bool]) -> None:
        self._allow_reply_func = func

    @iq_request_task
    def request_entity_time(self, jid: JID):
        _task = yield

        response = yield _make_request(jid)
        if response.isError():
            raise StanzaError(response)

        yield _parse_response(response)

    def _answer_request(
        self, _client: Client, stanza: Iq, _properties: IqProperties
    ) -> None:
        self._log.info("Request received from %s", stanza.getFrom())
        if not self._enabled:
            self._client.send_stanza(Error(stanza, ERR_SERVICE_UNAVAILABLE))
            raise NodeProcessed

        if self._allow_reply_func is not None:
            if not self._allow_reply_func(stanza.getFrom()):
                self._client.send_stanza(Error(stanza, ERR_FORBIDDEN))
                raise NodeProcessed

        time, tzo = get_local_time()
        iq = stanza.buildSimpleReply("result")
        time_node = iq.addChild("time", namespace=Namespace.TIME)
        time_node.setTagData("utc", time)
        time_node.setTagData("tzo", tzo)
        self._log.info("Send time: %s %s", time, tzo)
        self._client.send_stanza(iq)
        raise NodeProcessed


def _make_request(jid: JID) -> Iq:
    iq = Iq("get", to=jid)
    iq.addChild("time", namespace=Namespace.TIME)
    return iq


def _parse_response(response: Iq) -> str:
    time_ = response.getTag("time")
    if not time_:
        raise MalformedStanzaError("time node missing", response)

    tzo = time_.getTagData("tzo")
    if not tzo:
        raise MalformedStanzaError("tzo node or data missing", response)

    remote_tz = create_tzinfo(tz_string=tzo)
    if remote_tz is None:
        raise MalformedStanzaError("invalid tzo data", response)

    utc_time = time_.getTagData("utc")
    if not utc_time:
        raise MalformedStanzaError("utc node or data missing", response)

    date_time = parse_datetime(utc_time, check_utc=True)
    if date_time is None:
        raise MalformedStanzaError("invalid timezone definition", response)

    date_time = date_time.astimezone(remote_tz)
    return date_time.strftime("%c %Z")
