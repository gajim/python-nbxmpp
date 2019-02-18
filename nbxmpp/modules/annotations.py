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

import logging

from nbxmpp.protocol import NS_PRIVATE
from nbxmpp.protocol import NS_ROSTERNOTES
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Node
from nbxmpp.protocol import isResultNode
from nbxmpp.structs import AnnotationNote
from nbxmpp.structs import CommonResult
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.util import validate_jid
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error

log = logging.getLogger('nbxmpp.m.annotations')


class Annotations:
    def __init__(self, client):
        self._client = client
        self.handlers = []

    @property
    def domain(self):
        return self._client.get_bound_jid().getDomain()

    @call_on_response('_annotations_received')
    def request_annotations(self):
        log.info('Request annotations for %s', self.domain)
        payload = Node('storage', attrs={'xmlns': NS_ROSTERNOTES})
        return Iq(typ='get', queryNS=NS_PRIVATE, payload=payload)

    @callback
    def _annotations_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)

        storage = stanza.getQueryChild('storage')
        if storage is None:
            return raise_error(log.warning, stanza, 'stanza-malformed',
                               'No annotations found')

        nodes = storage.getTags('note')
        if not nodes:
            return raise_error(log.info, stanza, 'is-empty',
                               'No annotations found')

        notes = []
        for note in nodes:
            try:
                jid = validate_jid(note.getAttr('jid'))
            except Exception:
                log.warning('Invalid JID: %s, ignoring it',
                            note.getAttr('jid'))
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

        log.info('Received annotations from %s:', self.domain)
        for note in notes:
            log.info(notes)
        return notes

    @call_on_response('_default_response')
    def set_annotations(self, notes):
        log.info('Set annotations for %s:', self.domain)
        for note in notes:
            log.info(note)
        storage = Node('storage', attrs={'xmlns': NS_ROSTERNOTES})
        for note in notes:
            node = Node('note', attrs={'jid': note.jid})
            node.setData(note.data)
            if note.cdate is not None:
                node.setAttr('cdate', note.cdate)
            if note.mdate is not None:
                node.setAttr('mdate', note.mdate)
            storage.addChild(node=node)
        return Iq(typ='set', queryNS=NS_PRIVATE, payload=storage)

    @callback
    def _default_response(self, stanza):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)
        return CommonResult(jid=stanza.getFrom())
