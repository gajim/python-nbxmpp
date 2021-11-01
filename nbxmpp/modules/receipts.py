# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
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

from typing import Any

from nbxmpp import types
from nbxmpp.builder import Message
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import isMucPM
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import ReceiptData
from nbxmpp.util import generate_id
from nbxmpp.modules.base import BaseModule


class Receipts(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_receipt,
                          ns=Namespace.RECEIPTS,
                          priority=15),
        ]

    def _process_message_receipt(self,
                                 _client: types.Client,
                                 stanza: types.Message,
                                 properties: Any):

        request = stanza.find_tag('request', namespace=Namespace.RECEIPTS)
        if request is not None:
            properties.receipt = ReceiptData(request.localname)
            return

        received = stanza.find_tag('received', namespace=Namespace.RECEIPTS)
        if received is not None:
            id_ = received.get('id')
            if id_ is None:
                self._log.warning('Receipt without id attr')
                self._log.warning(stanza)
                return

            properties.receipt = ReceiptData(received.localname, id_)


def build_receipt(stanza: types.Message) -> types.Message:
    if stanza.localname == 'message':
        raise ValueError('Stanza type must be protocol.Message')

    if stanza.get('type') == 'error':
        raise ValueError('Receipt can not be generated for type error messages')

    if stanza.get('id') is None:
        raise ValueError('Receipt can not be generated for messages without id')

    if stanza.find_tag('received', namespace=Namespace.RECEIPTS) is not None:
        raise ValueError('Receipt can not be generated for receipts')

    is_muc_pm = isMucPM(stanza)

    jid = stanza.get_from()
    typ = stanza.get('type')
    if typ == 'groupchat' or not is_muc_pm:
        jid = jid.new_as_bare()

    message = Message(to=jid, type=typ)
    if is_muc_pm:
        message.add_tag('x', namespace=Namespace.MUC_USER)
    message_id = generate_id()
    message.set('id', message_id)
    message.add_tag('received', namespace=Namespace.RECEIPTS, id=stanza.get('id'))
    message.add_tag('store', namespace=Namespace.HINTS)
    message.add_tag('origin-id', namespace=Namespace.SID, id=val)

    return message
