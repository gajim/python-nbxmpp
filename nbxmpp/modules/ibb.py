# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import ERR_BAD_REQUEST
from nbxmpp.protocol import ERR_FEATURE_NOT_IMPLEMENTED
from nbxmpp.protocol import Error as ErrorStanza
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Node
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import IBBData
from nbxmpp.structs import IqProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task
from nbxmpp.util import b64decode
from nbxmpp.util import b64encode

if TYPE_CHECKING:
    from nbxmpp.client import Client


class IBB(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="iq", callback=self._process_ibb, ns=Namespace.IBB, priority=20
            ),
        ]

    def _process_ibb(
        self, _client: Client, stanza: Iq, properties: IqProperties
    ) -> None:
        if properties.type.is_set:
            open_ = stanza.getTag("open", namespace=Namespace.IBB)
            if open_ is not None:
                properties.ibb = self._parse_open(stanza, open_)
                return

            close = stanza.getTag("close", namespace=Namespace.IBB)
            if close is not None:
                properties.ibb = self._parse_close(stanza, close)
                return

            data = stanza.getTag("data", namespace=Namespace.IBB)
            if data is not None:
                properties.ibb = self._parse_data(stanza, data)
                return

    def _parse_open(self, stanza: Iq, open_: Node) -> IBBData:
        attrs = open_.getAttrs()
        try:
            block_size = int(attrs.get("block-size"))
        except Exception as error:
            self._log.warning(error)
            self._log.warning(stanza)
            self._client.send_stanza(ErrorStanza(stanza, ERR_BAD_REQUEST))
            raise NodeProcessed

        if block_size > 65535:
            self._log.warning("Invalid block-size")
            self._client.send_stanza(ErrorStanza(stanza, ERR_BAD_REQUEST))
            raise NodeProcessed

        sid = attrs.get("sid")
        if not sid:
            self._log.warning("Invalid sid")
            self._client.send_stanza(ErrorStanza(stanza, ERR_BAD_REQUEST))
            raise NodeProcessed

        type_ = attrs.get("stanza")
        if type_ == "message":
            self._client.send_stanza(ErrorStanza(stanza, ERR_FEATURE_NOT_IMPLEMENTED))
            raise NodeProcessed

        return IBBData(type="open", block_size=block_size, sid=sid)

    def _parse_close(self, stanza: Iq, close: Node) -> IBBData:
        sid = close.getAttrs().get("sid")
        if sid is None:
            self._log.warning("Invalid sid")
            self._client.send_stanza(ErrorStanza(stanza, ERR_BAD_REQUEST))
            raise NodeProcessed
        return IBBData(type="close", sid=sid)

    def _parse_data(self, stanza: Iq, data: Node) -> IBBData:
        attrs = data.getAttrs()

        sid = attrs.get("sid")
        if sid is None:
            self._log.warning("Invalid sid")
            self._client.send_stanza(ErrorStanza(stanza, ERR_BAD_REQUEST))
            raise NodeProcessed

        try:
            seq = int(attrs.get("seq"))
        except Exception:
            self._log.exception("Invalid seq")
            self._client.send_stanza(ErrorStanza(stanza, ERR_BAD_REQUEST))
            raise NodeProcessed

        try:
            decoded_data = b64decode(data.getData())
        except Exception:
            self._log.exception("Failed to decode IBB data")
            self._client.send_stanza(ErrorStanza(stanza, ERR_BAD_REQUEST))
            raise NodeProcessed

        return IBBData(type="data", sid=sid, seq=seq, data=decoded_data)

    def send_reply(self, stanza: Iq, error: str | None = None) -> None:
        if error is None:
            reply = stanza.buildReply("result")
            reply.getChildren().clear()
        else:
            reply = ErrorStanza(stanza, error)
        self._client.send_stanza(reply)

    @iq_request_task
    def send_open(self, jid: str, sid: str, block_size: int):
        _task = yield

        response = yield _make_ibb_open(jid, sid, block_size)
        yield process_response(response)

    @iq_request_task
    def send_close(self, jid: str, sid: str):
        _task = yield

        response = yield _make_ibb_close(jid, sid)
        yield process_response(response)

    @iq_request_task
    def send_data(self, jid: str, sid: str, seq: int, data: bytes):
        _task = yield

        response = yield _make_ibb_data(jid, sid, seq, data)
        yield process_response(response)


def _make_ibb_open(jid: str, sid: str, block_size: int) -> Iq:
    iq = Iq("set", to=jid)
    iq.addChild(
        "open",
        {"block-size": block_size, "sid": sid, "stanza": "iq"},
        namespace=Namespace.IBB,
    )
    return iq


def _make_ibb_close(jid: str, sid: str) -> Iq:
    iq = Iq("set", to=jid)
    iq.addChild("close", {"sid": sid}, namespace=Namespace.IBB)
    return iq


def _make_ibb_data(jid: str, sid: str, seq: int, data: bytes) -> Iq:
    iq = Iq("set", to=jid)
    ibb_data = iq.addChild("data", {"sid": sid, "seq": seq}, namespace=Namespace.IBB)
    ibb_data.setData(b64encode(data))
    return iq
