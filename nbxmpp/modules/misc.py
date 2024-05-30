# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from nbxmpp.modules.delay import parse_delay
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import InvalidFrom
from nbxmpp.protocol import InvalidStanza
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import Protocol
from nbxmpp.structs import CarbonData
from nbxmpp.structs import MAMData

log = logging.getLogger("nbxmpp.m.misc")


def unwrap_carbon(
    stanza: Protocol, own_jid: JID
) -> tuple[Message | Protocol, CarbonData | None]:
    carbon = stanza.getTag("received", namespace=Namespace.CARBONS)
    if carbon is None:
        carbon = stanza.getTag("sent", namespace=Namespace.CARBONS)
        if carbon is None:
            return stanza, None

    # Carbon must be from our bare jid
    if stanza.getFrom() != own_jid.new_as_bare():
        raise InvalidFrom("Invalid from: %s" % stanza.getAttr("from"))

    forwarded = carbon.getTag("forwarded", namespace=Namespace.FORWARD)
    message = Message(node=forwarded.getTag("message"))

    type_ = carbon.getName()

    # Fill missing to/from
    to = message.getTo()
    if to is None:
        message.setTo(own_jid.bare)

    frm = message.getFrom()
    if frm is None:
        message.setFrom(own_jid.bare)

    if type_ == "received":
        if message.getFrom().bare_match(own_jid):
            # Drop 'received' Carbons from ourself, we already
            # got the message with the 'sent' Carbon or via the
            # message itself
            raise NodeProcessed('Drop "received"-Carbon from ourself')

        if message.getTag("x", namespace=Namespace.MUC_USER) is not None:
            # A MUC broadcasts messages sent to us to all resources
            # there is no need to process the received carbon
            raise NodeProcessed('Drop MUC-PM "received"-Carbon')

    return message, CarbonData(type=type_)


def unwrap_mam(
    stanza: Protocol, own_jid: JID
) -> tuple[Message | Protocol, MAMData | None]:
    result = stanza.getTag("result", namespace=Namespace.MAM_2)
    if result is None:
        result = stanza.getTag("result", namespace=Namespace.MAM_1)
        if result is None:
            return stanza, None

    query_id = result.getAttr("queryid")
    if query_id is None:
        log.warning("No queryid on MAM message")
        log.warning(stanza)
        raise InvalidStanza

    id_ = result.getAttr("id")
    if id_ is None:
        log.warning("No id on MAM message")
        log.warning(stanza)
        raise InvalidStanza

    forwarded = result.getTag("forwarded", namespace=Namespace.FORWARD)
    message = Message(node=forwarded.getTag("message"))

    # Fill missing to/from
    to = message.getTo()
    if to is None:
        message.setTo(own_jid.bare)

    frm = message.getFrom()
    if frm is None:
        message.setFrom(own_jid.bare)

    # Timestamp parsing
    # Most servers dont set the 'from' attr, so we cant check for it
    delay_timestamp = parse_delay(forwarded, epoch=True)
    if delay_timestamp is None:
        log.warning("No timestamp on MAM message")
        log.warning(stanza)
        raise InvalidStanza

    return message, MAMData(
        id=id_,
        query_id=query_id,
        archive=stanza.getFrom(),
        namespace=result.getNamespace(),
        timestamp=delay_timestamp,
    )


def build_xhtml_body(xhtml: str, xmllang: str | None = None) -> str | None:
    try:
        if xmllang is not None:
            body = '<body xmlns="%s" xml:lang="%s">%s</body>' % (
                Namespace.XHTML,
                xmllang,
                xhtml,
            )
        else:
            body = '<body xmlns="%s">%s</body>' % (Namespace.XHTML, xhtml)
    except Exception as error:
        log.error("Error while building xhtml node: %s", error)
        return None
    return body
