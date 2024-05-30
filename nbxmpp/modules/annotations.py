# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.modules.util import process_response
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.protocol import Node
from nbxmpp.structs import AnnotationNote
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Annotations(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @property
    def domain(self) -> str | None:
        return self._client.get_bound_jid().domain

    @iq_request_task
    def request_annotations(self):
        _task = yield

        response = yield _make_request()
        if response.isError():
            raise StanzaError(response)

        query = response.getQuery()
        storage = query.getTag("storage", namespace=Namespace.ROSTERNOTES)
        if storage is None:
            raise MalformedStanzaError("storage node missing", response)

        notes: list[AnnotationNote] = []
        for note in storage.getTags("note"):
            try:
                jid = JID.from_string(note.getAttr("jid"))
            except Exception as error:
                self._log.warning("Invalid JID: %s, %s", note.getAttr("jid"), error)
                continue

            cdate = note.getAttr("cdate")
            if cdate is not None:
                cdate = parse_datetime(cdate, epoch=True)

            mdate = note.getAttr("mdate")
            if mdate is not None:
                mdate = parse_datetime(mdate, epoch=True)

            data = note.getData()
            notes.append(AnnotationNote(jid=jid, cdate=cdate, mdate=mdate, data=data))

        self._log.info("Received annotations from %s:", self.domain)
        for note in notes:
            self._log.info(note)
        yield notes

    @iq_request_task
    def set_annotations(self, notes: list[AnnotationNote]):
        _task = yield

        for note in notes:
            self._log.info(note)

        response = yield _make_set_request(notes)
        yield process_response(response)


def _make_request() -> Iq:
    payload = Node("storage", attrs={"xmlns": Namespace.ROSTERNOTES})
    return Iq(typ="get", queryNS=Namespace.PRIVATE, payload=payload)


def _make_set_request(notes: list[AnnotationNote]) -> Iq:
    storage = Node("storage", attrs={"xmlns": Namespace.ROSTERNOTES})
    for note in notes:
        node = Node("note", attrs={"jid": note.jid})
        node.setData(note.data)
        if note.cdate is not None:
            node.setAttr("cdate", note.cdate)
        if note.mdate is not None:
            node.setAttr("mdate", note.mdate)
        storage.addChild(node=node)
    return Iq(typ="set", queryNS=Namespace.PRIVATE, payload=storage)
