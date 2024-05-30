# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.bookmarks.util import build_storage_node
from nbxmpp.modules.bookmarks.util import get_private_request
from nbxmpp.modules.bookmarks.util import parse_private_bookmarks
from nbxmpp.modules.util import process_response
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.structs import BookmarkData
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client


class PrivateBookmarks(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def request_bookmarks(self):
        _task = yield

        response = yield get_private_request()
        if response.isError():
            raise StanzaError(response)

        bookmarks = parse_private_bookmarks(response, self._log)
        for bookmark in bookmarks:
            self._log.info(bookmark)

        yield bookmarks

    @iq_request_task
    def store_bookmarks(self, bookmarks: list[BookmarkData]):
        _task = yield

        self._log.info("Store Bookmarks")

        storage_node = build_storage_node(bookmarks)
        response = yield Iq("set", Namespace.PRIVATE, payload=storage_node)
        yield process_response(response)
