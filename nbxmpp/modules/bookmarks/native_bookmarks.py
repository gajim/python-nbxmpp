# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.errors import MalformedStanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.bookmarks.util import build_conference_node
from nbxmpp.modules.bookmarks.util import parse_bookmark
from nbxmpp.modules.util import finalize
from nbxmpp.modules.util import raise_if_error
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import BookmarkData
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client

BOOKMARK_OPTIONS = {
    "pubsub#notify_delete": "true",
    "pubsub#notify_retract": "true",
    "pubsub#persist_items": "true",
    "pubsub#max_items": "max",
    "pubsub#access_model": "whitelist",
    "pubsub#send_last_published_item": "never",
}


class NativeBookmarks(BaseModule):

    _depends = {
        "retract": "PubSub",
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
        self, _client: Client, _stanza: Message, properties: MessageProperties
    ) -> None:
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.BOOKMARKS_1:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        try:
            bookmark_item = parse_bookmark(item)
        except MalformedStanzaError as error:
            self._log.warning(error)
            self._log.warning(error.stanza)
            raise NodeProcessed

        pubsub_event = properties.pubsub_event._replace(data=bookmark_item)
        self._log.info("Received bookmark item from: %s", properties.jid)
        self._log.info(bookmark_item)

        properties.pubsub_event = pubsub_event

    @iq_request_task
    def request_bookmarks(self):
        _task = yield

        items = yield self.request_items(Namespace.BOOKMARKS_1)
        raise_if_error(items)

        bookmarks: list[BookmarkData] = []
        for item in items:
            try:
                bookmark_item = parse_bookmark(item)
            except MalformedStanzaError as error:
                self._log.warning(error)
                self._log.warning(error.stanza)
                continue

            bookmarks.append(bookmark_item)

        for bookmark in bookmarks:
            self._log.info(bookmark)

        yield bookmarks

    @iq_request_task
    def retract_bookmark(self, bookmark_jid: JID):
        task = yield

        self._log.info("Retract Bookmark: %s", bookmark_jid)

        result = yield self.retract(Namespace.BOOKMARKS_1, str(bookmark_jid))
        yield finalize(task, result)

    @iq_request_task
    def store_bookmarks(self, bookmarks: list[BookmarkData]):
        _task = yield

        self._log.info("Store Bookmarks")

        for bookmark in bookmarks:
            self.publish(
                Namespace.BOOKMARKS_1,
                build_conference_node(bookmark),
                id_=str(bookmark.jid),
                options=BOOKMARK_OPTIONS,
                force_node_options=True,
            )

        yield True
