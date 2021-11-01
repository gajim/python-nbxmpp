# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Union
from typing import Generator

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.builder import Iq
from nbxmpp.jid import JID
from nbxmpp.structs import AnnotationNote, CommonResult
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response
from nbxmpp.modules.date_and_time import parse_datetime


RequestGenerator = Generator[Union[types.Iq, list[AnnotationNote]],
                             types.Iq,
                             None]


SetGenerator = Generator[Union[types.Iq, CommonResult],
                         types.Iq,
                         None]


class Annotations(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @property
    def domain(self):
        return self._client.get_bound_jid().domain

    @iq_request_task
    def request_annotations(self) -> RequestGenerator:

        response = yield _make_request()
        if response.is_error():
            raise StanzaError(response)

        query = response.get_query(namespace=Namespace.PRIVATE)
        storage = query.find_tag('storage', namespace=Namespace.ROSTERNOTES)
        if storage is None:
            raise MalformedStanzaError('storage node missing', response)

        notes: list[AnnotationNote] = []
        for note in storage.find_tags('note'):
            try:
                jid = JID.from_string(note.get('jid'))
            except Exception as error:
                self._log.warning('Invalid JID: %s, %s',
                                  note.get('jid'), error)
                continue

            cdate = note.get('cdate')
            if cdate is not None:
                cdate = parse_datetime(cdate, epoch=True)

            mdate = note.get('mdate')
            if mdate is not None:
                mdate = parse_datetime(mdate, epoch=True)

            data = note.text or ''
            notes.append(AnnotationNote(jid=jid, cdate=cdate,
                                        mdate=mdate, data=data))

        self._log.info('Received annotations from %s:', self.domain)
        for note in notes:
            self._log.info(note)
        yield notes

    @iq_request_task
    def set_annotations(self, notes: list[AnnotationNote]) -> SetGenerator:

        for note in notes:
            self._log.info(note)

        response = yield _make_set_request(notes)
        yield process_response(response)


def _make_request() -> types.Iq:
    iq = Iq()
    query = iq.add_tag('query', namespace=Namespace.PRIVATE)
    query.add_tag('storage', namespace=Namespace.ROSTERNOTES)
    return iq


def _make_set_request(notes: list[AnnotationNote]) -> types.Iq:
    iq = Iq(type='set')
    query = iq.add_query(namespace=Namespace.PRIVATE)
    storage = query.add_tag('storage', namespace=Namespace.ROSTERNOTES)

    for note in notes:
        note_tag = storage.add_tag('note', jid=str(note.jid))
        note_tag.text = note.data
        if note.cdate is not None:
            note_tag.set('cdate', note.cdate)
        if note.mdate is not None:
            note_tag.set('mdate', note.mdate)

    return iq
