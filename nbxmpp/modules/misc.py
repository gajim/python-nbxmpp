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

from typing import Optional
from typing import cast

import logging

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.exceptions import InvalidFrom
from nbxmpp.exceptions import InvalidStanza
from nbxmpp.jid import JID
from nbxmpp.structs import MAMData
from nbxmpp.structs import CarbonData
from nbxmpp.modules.delay import parse_delay


log = logging.getLogger('nbxmpp.m.misc')


def unwrap_carbon(stanza: types.Message, own_jid: JID):
    carbon = stanza.find_tag('received', namespace=Namespace.CARBONS)
    if carbon is None:
        carbon = stanza.find_tag('sent', namespace=Namespace.CARBONS)
        if carbon is None:
            return stanza, None

    # Carbon must be from our bare jid
    if stanza.get_from() != own_jid.new_as_bare():
        raise InvalidFrom('Invalid from: %s' % stanza.get('from'))

    forwarded = carbon.find_tag('forwarded', namespace=Namespace.FORWARD)
    message = forwarded.find_tag('message')

    message = cast(types.Message, message)
    type_ = carbon.localname

    # Fill missing to/from
    to = message.get_to()
    if to is None:
        message.set_to(own_jid.bare)

    frm = message.get_from()
    if frm is None:
        message.set_from(own_jid.bare)

    if type_ == 'received':
        if message.get_from().bare_match(own_jid):
            # Drop 'received' Carbons from ourself, we already
            # got the message with the 'sent' Carbon or via the
            # message itself
            raise NodeProcessed('Drop "received"-Carbon from ourself')

        if message.find_tag('x', namespace=Namespace.MUC_USER) is not None:
            # A MUC broadcasts messages sent to us to all resources
            # there is no need to process the received carbon
            raise NodeProcessed('Drop MUC-PM "received"-Carbon')

    return message, CarbonData(type=type_)


def unwrap_mam(stanza: types.Message, own_jid: JID) -> tuple[types.Message, Optional[MAMData]]:
    result = stanza.find_tag('result', namespace=Namespace.MAM_2)
    if result is None:
        result = stanza.find_tag('result', namespace=Namespace.MAM_1)
        if result is None:
            return stanza, None

    query_id = result.get('queryid')
    if query_id is None:
        log.warning('No queryid on MAM message')
        log.warning(stanza)
        raise InvalidStanza

    id_ = result.get('id')
    if id_ is None:
        log.warning('No id on MAM message')
        log.warning(stanza)
        raise InvalidStanza

    forwarded = result.find_tag('forwarded', namespace=Namespace.FORWARD)
    message = forwarded.find_tag('message')

    message = cast(types.Message, message)

    # Fill missing to/from
    to = message.get_to()
    if to is None:
        message.set_to(own_jid.bare)

    frm = message.get_from()
    if frm is None:
        message.set_from(own_jid.bare)

    # Timestamp parsing
    # Most servers dont set the 'from' attr, so we cant check for it
    delay_timestamp = parse_delay(forwarded)
    if delay_timestamp is None:
        log.warning('No timestamp on MAM message')
        log.warning(stanza)
        raise InvalidStanza

    return message, MAMData(id=id_,
                            query_id=query_id,
                            archive=stanza.get_from(),
                            namespace=result.namespace,
                            timestamp=delay_timestamp)


def build_xhtml_body(xhtml: str,
                     xmllang: Optional[str] = None) -> Optional[str]:
    try:
        if xmllang is not None:
            body = '<body xmlns="%s" xml:lang="%s">%s</body>' % (
                Namespace.XHTML, xmllang, xhtml)
        else:
            body = '<body xmlns="%s">%s</body>' % (Namespace.XHTML, xhtml)
    except Exception as error:
        log.error('Error while building xhtml node: %s', error)
        return None
    return body
