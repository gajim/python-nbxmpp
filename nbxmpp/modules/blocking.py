# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from collections.abc import Generator

from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.simplexml import Node
from nbxmpp.structs import BlockingProperties
from nbxmpp.structs import BlockingPush
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task
from nbxmpp.types import BlockingReportValues

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Blocking(BaseModule):
    def __init__(self, client: Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="iq",
                priority=15,
                callback=self._process_blocking_push,
                typ="set",
                ns=Namespace.BLOCKING,
            ),
        ]

    @iq_request_task
    def request_blocking_list(self) -> Generator[set[JID] | Iq | None, Iq]:
        _task = yield

        result = yield _make_blocking_list_request()
        if result.isError():
            raise StanzaError(result)

        blocklist = result.getTag("blocklist", namespace=Namespace.BLOCKING)
        if blocklist is None:
            raise MalformedStanzaError("blocklist node missing", result)

        blocked: set[JID] = set()
        for item in blocklist.getTags("item"):
            try:
                jid = JID.from_string(item.getAttr("jid"))
            except Exception:
                self._log.info("Invalid JID: %s", item.getAttr("jid"))
                continue

            blocked.add(jid)

        self._log.info("Received blocking list: %s", blocked)
        yield blocked

    @iq_request_task
    def block(self, jids: list[JID], report: BlockingReportValues | None = None):

        _task = yield

        response = yield _make_block_request(jids, report)
        yield process_response(response)

    @iq_request_task
    def unblock(self, jids: list[JID]):
        _task = yield

        response = yield _make_unblock_request(jids)
        yield process_response(response)

    @staticmethod
    def _process_blocking_push(
        client: Client, stanza: Iq, properties: BlockingProperties
    ) -> None:

        unblock = stanza.getTag("unblock", namespace=Namespace.BLOCKING)
        if unblock is not None:
            properties.blocking = _parse_push(unblock)

        block = stanza.getTag("block", namespace=Namespace.BLOCKING)
        if block is not None:
            properties.blocking = _parse_push(block)

        reply = stanza.buildSimpleReply("result")
        client.send_stanza(reply)


def _make_blocking_list_request() -> Iq:
    iq = Iq("get", Namespace.BLOCKING)
    iq.setQuery("blocklist")
    return iq


def _make_block_request(jids: list[JID], report: BlockingReportValues | None) -> Iq:

    iq = Iq("set", Namespace.BLOCKING)
    query = iq.setQuery(name="block")
    for jid in jids:
        item = query.addChild(name="item", attrs={"jid": str(jid)})
        if report in ("spam", "abuse"):
            action = item.addChild(name="report", namespace=Namespace.REPORTING)
            action.setTag(report)
    return iq


def _make_unblock_request(jids: list[JID]) -> Iq:
    iq = Iq("set", Namespace.BLOCKING)
    query = iq.setQuery(name="unblock")
    for jid in jids:
        query.addChild(name="item", attrs={"jid": str(jid)})
    return iq


def _parse_push(node: Node) -> BlockingPush:
    items = node.getTags("item")
    if not items:
        return BlockingPush(block=set(), unblock=set(), unblock_all=True)

    jids: set[JID] = set()
    for item in items:
        jid = item.getAttr("jid")
        if not jid:
            continue

        try:
            jid = JID.from_string(jid)
        except Exception:
            continue

        jids.add(jid)

    block: set[JID] = set()
    unblock: set[JID] = set()
    if node.getName() == "block":
        block = jids
    else:
        unblock = jids

    return BlockingPush(block=block, unblock=unblock, unblock_all=False)
