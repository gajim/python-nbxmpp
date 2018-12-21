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

from nbxmpp.protocol import NS_CARBONS
from nbxmpp.protocol import NS_FORWARD
from nbxmpp.protocol import NS_MUC_USER
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import InvalidFrom
from nbxmpp.protocol import Message

log = logging.getLogger('nbxmpp.misc')


def unwrap_carbon(stanza, own_jid):
    carbon = stanza.getTag('received', namespace=NS_CARBONS)
    if carbon is None:
        carbon = stanza.getTag('sent', namespace=NS_CARBONS)
        if carbon is None:
            return stanza, None

    # Carbon must be from our bare jid
    if not stanza.getFrom() == own_jid.getBare():
        raise InvalidFrom('Invalid from: %s' % stanza.getAttr('from'))

    forwarded = carbon.getTag('forwarded', namespace=NS_FORWARD)
    message = Message(node=forwarded.getTag('message'))

    type_ = carbon.getName()
    to = message.getTo()
    if to is None:
        message.setTo(own_jid.getBare())

    frm = message.getFrom()
    if frm is None:
        message.setFrom(own_jid.getBare())

    if type_ == 'received':
        if message.getFrom().bareMatch(own_jid):
            # Drop 'received' Carbons from ourself, we already
            # got the message with the 'sent' Carbon or via the
            # message itself
            raise NodeProcessed('Drop "received"-Carbon from ourself')

        if message.getTag('x', namespace=NS_MUC_USER) is not None:
            # A MUC broadcasts messages sent to us to all resources
            # there is no need to process the received carbon
            raise NodeProcessed('Drop MUC-PM "received"-Carbon')

    return message, type_
