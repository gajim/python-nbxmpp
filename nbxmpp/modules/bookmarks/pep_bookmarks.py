# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.errors import MalformedStanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.bookmarks.util import build_storage_node
from nbxmpp.modules.bookmarks.util import parse_bookmarks
from nbxmpp.modules.util import raise_if_error
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import BookmarkData
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task

BOOKMARK_OPTIONS = {
    "pubsub#persist_items": "true",
    "pubsub#access_model": "whitelist",
}

if TYPE_CHECKING:
    from nbxmpp.client import Client


class PEPBookmarks(BaseModule):

    _depends = {
        "publish": "PubSub",
        "request_items": "PubSub",
    }

    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_pubsub_bookmarks,
                ns=Namespace.PUBSUB_EVENT,
                priority=16,
            ),
        ]

    def _process_pubsub_bookmarks(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.BOOKMARKS:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        try:
            bookmarks = parse_bookmarks(item, self._log)
        except MalformedStanzaError as error:
            self._log.warning(error)
            self._log.warning(stanza)
            raise NodeProcessed

        if not bookmarks:
            self._log.info("Bookmarks removed")
            return

        pubsub_event = properties.pubsub_event._replace(data=bookmarks)
        self._log.info("Received bookmarks from: %s", properties.jid)
        for bookmark in bookmarks:
            self._log.info(bookmark)

        properties.pubsub_event = pubsub_event

    @iq_request_task
    def request_bookmarks(self):
        _task = yield

        items = yield self.request_items(Namespace.BOOKMARKS, max_items=1)
        raise_if_error(items)

        if not items:
            yield []

        bookmarks = parse_bookmarks(items[0], self._log)
        for bookmark in bookmarks:
            self._log.info(bookmark)

        yield bookmarks

    @iq_request_task
    def store_bookmarks(self, bookmarks: list[BookmarkData]):
        _task = yield

        self._log.info("Store Bookmarks")

        self.publish(
            Namespace.BOOKMARKS,
            build_storage_node(bookmarks),
            id_="current",
            options=BOOKMARK_OPTIONS,
            force_node_options=True,
        )
