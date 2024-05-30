# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.errors import HTTPUploadStanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.structs import HTTPUploadData
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client

ALLOWED_HEADERS = ["Authorization", "Cookie", "Expires"]


class HTTPUpload(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def request_slot(self, jid: JID, filename: str, size: int, content_type: str):
        _task = yield

        response = yield _make_request(jid, filename, size, content_type)
        if response.isError():
            raise HTTPUploadStanzaError(response)

        slot = response.getTag("slot", namespace=Namespace.HTTPUPLOAD_0)
        if slot is None:
            raise MalformedStanzaError("slot node missing", response)

        put_uri = slot.getTagAttr("put", "url")
        if put_uri is None:
            raise MalformedStanzaError("put uri missing", response)

        get_uri = slot.getTagAttr("get", "url")
        if get_uri is None:
            raise MalformedStanzaError("get uri missing", response)

        headers: dict[str, str] = {}
        for header in slot.getTag("put").getTags("header"):
            name = header.getAttr("name")
            if name not in ALLOWED_HEADERS:
                raise MalformedStanzaError(
                    "not allowed header found: %s" % name, response
                )

            data = header.getData()
            if "\n" in data:
                raise MalformedStanzaError("newline in header data found", response)

            headers[name] = data

        yield HTTPUploadData(put_uri=put_uri, get_uri=get_uri, headers=headers)


def _make_request(jid: JID, filename: str, size: int, content_type: str) -> Iq:
    iq = Iq(typ="get", to=jid)
    attr = {"filename": filename, "size": size, "content-type": content_type}
    iq.setTag(name="request", namespace=Namespace.HTTPUPLOAD_0, attrs=attr)
    return iq
