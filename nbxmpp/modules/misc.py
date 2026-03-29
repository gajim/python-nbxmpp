from __future__ import annotations

from typing import cast

import logging

from nbxmpp.exceptions import InvalidFrom
from nbxmpp.exceptions import InvalidStanza
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.jid import JID
from nbxmpp.modules.delay import parse_delay
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import CarbonData
from nbxmpp.structs import MAMData

from .. import elements

log = logging.getLogger("nbxmpp.m.misc")


def unwrap_carbon(stanza: elements.Message, own_jid: JID):
    carbon = stanza.find_tag("received", namespace=Namespace.CARBONS)
    if carbon is None:
        carbon = stanza.find_tag("sent", namespace=Namespace.CARBONS)
        if carbon is None:
            return stanza, None

    # Carbon must be from our bare jid
    if stanza.get_from() != own_jid.new_as_bare():
        raise InvalidFrom("Invalid from: %s" % stanza.get("from"))

    forwarded = carbon.find_tag("forwarded", namespace=Namespace.FORWARD)
    message = forwarded.find_tag("message")

    message = cast(elements.Message, message)
    type_ = carbon.localname

    # Fill missing to/from
    to = message.get_to()
    if to is None:
        message.set_to(own_jid.bare)

    frm = message.get_from()
    if frm is None:
        message.set_from(own_jid.bare)

    if type_ == "received":
        if message.get_from().bare_match(own_jid):
            # Drop 'received' Carbons from ourself, we already
            # got the message with the 'sent' Carbon or via the
            # message itself
            raise NodeProcessed('Drop "received"-Carbon from ourself')

        if message.find_tag("x", namespace=Namespace.MUC_USER) is not None:
            # A MUC broadcasts messages sent to us to all resources
            # there is no need to process the received carbon
            raise NodeProcessed('Drop MUC-PM "received"-Carbon')

    return message, CarbonData(type=type_)


def unwrap_mam(
    stanza: elements.Message, own_jid: JID
) -> tuple[elements.Message, MAMData | None]:
    result = stanza.find_tag("result", namespace=Namespace.MAM_2)
    if result is None:
        result = stanza.find_tag("result", namespace=Namespace.MAM_1)
        if result is None:
            return stanza, None

    query_id = result.get("queryid")
    if query_id is None:
        log.warning("No queryid on MAM message")
        log.warning(stanza)
        raise InvalidStanza

    id_ = result.get("id")
    if id_ is None:
        log.warning("No id on MAM message")
        log.warning(stanza)
        raise InvalidStanza

    forwarded = result.find_tag("forwarded", namespace=Namespace.FORWARD)
    message = forwarded.find_tag("message")

    message = cast(elements.Message, message)

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
        log.warning("No timestamp on MAM message")
        log.warning(stanza)
        raise InvalidStanza

    return message, MAMData(
        id=id_,
        query_id=query_id,
        archive=stanza.get_from(),
        namespace=result.namespace,
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
