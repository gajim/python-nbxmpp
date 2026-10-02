# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any
from typing import TYPE_CHECKING

from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.dataforms import MultipleDataForm
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.modules.util import finalize
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.protocol import Node
from nbxmpp.structs import SearchFields
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client


FIELDS = [
    "instructions",
    "first",
    "last",
    "nick",
    "email",
]


class Search(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self.handlers = []
        self._client = client

    @iq_request_task
    def request_form(self, jid: JID) -> Any:
        _task = yield

        iq = Iq(typ="get", to=jid, queryNS=Namespace.SEARCH)

        response = yield iq
        if response.isError():
            raise StanzaError(response)

        query = response.getTag("query", namespace=Namespace.SEARCH)
        if query is None:
            raise MalformedStanzaError("no query node found", response)

        dataform = query.getTag("x", namespace=Namespace.DATA)
        if dataform is None:
            yield parse_simple_fields(query)
        else:
            yield finalize(_task, SimpleDataForm(extend=dataform))

    @iq_request_task
    def send_form(self, jid: JID, form: SimpleDataForm | SearchFields) -> Any:
        _task = yield

        iq = Iq(typ="set", to=jid, queryNS=Namespace.SEARCH)
        item = iq.setQuery()
        if isinstance(form, SearchFields):
            for field, value in form:
                item.setTagData(field, value)
        else:
            item.addChild(node=form)

        response = yield iq
        if response.isError():
            raise StanzaError(response)

        query = response.getTag("query", namespace=Namespace.SEARCH)
        if query is None:
            raise MalformedStanzaError("no query node found", response)

        dataform = query.getTag("x", namespace=Namespace.DATA)
        if dataform is None:
            yield finalize(_task, MultipleDataForm(extend=dataform))

        else:
            raise MalformedStanzaError("only dataforms supported", response)


def parse_simple_fields(query: Node) -> SearchFields:
    data: dict[str, str] = {}
    for child in query.getChildren():
        if not isinstance(child, Node):
            continue
        name = child.getName()
        if name not in FIELDS:
            continue

        data[name] = child.getData()

    return SearchFields(**data)
