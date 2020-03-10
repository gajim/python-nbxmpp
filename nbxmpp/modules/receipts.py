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

import logging

from nbxmpp.protocol import NS_RECEIPTS
from nbxmpp.protocol import NS_MUC_USER
from nbxmpp.protocol import isMucPM
from nbxmpp.protocol import Message
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import ReceiptData
from nbxmpp.util import generate_id

log = logging.getLogger('nbxmpp.m.receipts')


class Receipts:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_receipt,
                          ns=NS_RECEIPTS,
                          priority=15),
        ]

    def _process_message_receipt(self, _client, stanza, properties):
        request = stanza.getTag('request', namespace=NS_RECEIPTS)
        if request is not None:
            properties.receipt = ReceiptData(request.getName())
            return

        received = stanza.getTag('received', namespace=NS_RECEIPTS)
        if received is not None:
            id_ = received.getAttr('id')
            if id_ is None:
                log.warning('Receipt without id attr')
                log.warning(stanza)
                return

            properties.receipt = ReceiptData(received.getName(), id_)


def build_receipt(stanza):
    if not isinstance(stanza, Message):
        raise ValueError('Stanza type must be protocol.Message')

    if stanza.getType() == 'error':
        raise ValueError('Receipt can not be generated for type error messages')

    if stanza.getID() is None:
        raise ValueError('Receipt can not be generated for messages without id')

    if stanza.getTag('received', namespace=NS_RECEIPTS) is not None:
        raise ValueError('Receipt can not be generated for receipts')

    is_muc_pm = isMucPM(stanza)

    jid = stanza.getFrom().copy()
    typ = stanza.getType()
    if typ == 'groupchat' or not is_muc_pm:
        jid.setBare()

    message = Message(to=jid, typ=typ)
    if is_muc_pm:
        message.setTag('x', namespace=NS_MUC_USER)
    message_id = generate_id()
    message.setID(message_id)
    message.setReceiptReceived(stanza.getID())
    message.setHint('store')
    message.setOriginID(message_id)
    return message