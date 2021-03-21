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

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Node
from nbxmpp.protocol import JID
from nbxmpp.structs import AnnotationNote
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response
from nbxmpp.modules.date_and_time import parse_datetime


class Annotations(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @property
    def domain(self):
        return self._client.get_bound_jid().domain

    @iq_request_task
    def request_annotations(self):
        _task = yield

        response = yield _make_request()
        if response.isError():
            raise StanzaError(response)

        query = response.getQuery()
        storage = query.getTag('storage', namespace=Namespace.ROSTERNOTES)
        if storage is None:
            raise MalformedStanzaError('storage node missing', response)

        notes = []
        for note in storage.getTags('note'):
            try:
                jid = JID.from_string(note.getAttr('jid'))
            except Exception as error:
                self._log.warning('Invalid JID: %s, %s',
                                  note.getAttr('jid'), error)
                continue

            cdate = note.getAttr('cdate')
            if cdate is not None:
                cdate = parse_datetime(cdate, epoch=True)

            mdate = note.getAttr('mdate')
            if mdate is not None:
                mdate = parse_datetime(mdate, epoch=True)

            data = note.getData()
            notes.append(AnnotationNote(jid=jid, cdate=cdate,
                                        mdate=mdate, data=data))

        self._log.info('Received annotations from %s:', self.domain)
        for note in notes:
            self._log.info(note)
        yield notes

    @iq_request_task
    def set_annotations(self, notes):
        _task = yield

        for note in notes:
            self._log.info(note)

        response = yield _make_set_request(notes)
        yield process_response(response)


def _make_request():
    payload = Node('storage', attrs={'xmlns': Namespace.ROSTERNOTES})
    return Iq(typ='get', queryNS=Namespace.PRIVATE, payload=payload)

def _make_set_request(notes):
    storage = Node('storage', attrs={'xmlns': Namespace.ROSTERNOTES})
    for note in notes:
        node = Node('note', attrs={'jid': note.jid})
        node.setData(note.data)
        if note.cdate is not None:
            node.setAttr('cdate', note.cdate)
        if note.mdate is not None:
            node.setAttr('mdate', note.mdate)
        storage.addChild(node=node)
    return Iq(typ='set', queryNS=Namespace.PRIVATE, payload=storage)
