# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp import elements
from nbxmpp import exceptions
from nbxmpp.const import MessageType
from nbxmpp.jid import JID
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.fallback import parse_fallback_indication
from nbxmpp.modules.misc import unwrap_carbon
from nbxmpp.modules.misc import unwrap_mam
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import BodyData
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import PreparationHandler
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import StanzaIDData
from nbxmpp.structs import XHTMLData
from nbxmpp.util import error_factory

if TYPE_CHECKING:
    from nbxmpp.client import Client


class BaseMessage(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            PreparationHandler(
                name="message", callback=self._process_message_preparation, priority=10
            ),
            StanzaHandler(
                name="message", callback=self._process_message_base, priority=5
            ),
            StanzaHandler(
                name="message", callback=self._process_message_after_base, priority=10
            ),
        ]

    def _process_message_preparation(
        self, _client: Client, element: elements.Message, properties: MessageProperties
    ) -> None:
        # set default type attr
        if element.get("type") is None:
            element.set("type", "normal")

        # https://tools.ietf.org/html/rfc6120#section-8.1.1.1
        # If the stanza does not include a 'to' address then the client MUST
        # treat it as if the 'to' address were included with a value of the
        # client's full JID.

        own_jid = self._client.get_bound_jid()
        assert own_jid is not None

        to = element.get_to()
        if to is None:
            element.set_to(own_jid)

        elif not to.bare_match(own_jid):
            self._log.warning("Message addressed to someone else: %s", element)
            return

        if element.get_from() is None:
            element.set_from(own_jid.bare)

        try:
            element, properties.carbon = unwrap_carbon(element, own_jid)
        except (exceptions.InvalidFrom, exceptions.InvalidJid) as exc:
            self._log.warning(exc)
            self._log.warning(element)
            return
        except exceptions.NodeProcessed as exc:
            self._log.info(exc)
            return

        try:
            element, properties.mam = unwrap_mam(element, own_jid)
        except (exceptions.InvalidStanza, exceptions.InvalidJid) as exc:
            self._log.warning(exc)
            self._log.warning(element)
            return

    def _process_message_base(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        # if to := stanza.get_to():
        #     if to.bare_match(own_jid):
        #         self._log.warning("Message addressed to someone else: %s", stanza)
        #         raise NodeProcessed

        properties.type = self._parse_type(stanza)

        if properties.is_carbon_message and properties.carbon.is_sent:
            properties.jid = stanza.getTo()

        elif properties.is_mam_message and not properties.type.is_groupchat:
            own_jid = self._client.get_bound_jid()
            if own_jid.bare_match(stanza.getFrom()):
                properties.jid = stanza.getTo()
            else:
                properties.jid = stanza.getFrom()

        else:
            properties.jid = stanza.getFrom()

        self._parse_if_private_message(stanza, properties)

        properties.remote_jid = self._determine_remote_jid(properties)
        properties.from_ = stanza.getFrom()
        properties.to = stanza.getTo()
        properties.id = stanza.getID()
        properties.self_message = self._parse_self_message(stanza, properties)

        properties.origin_id = stanza.getOriginID()
        properties.stanza_ids = self._parse_stanza_ids(stanza)

        if properties.type.is_error:
            properties.error = error_factory(stanza)

    def _determine_remote_jid(self, properties: MessageProperties) -> JID | None:
        if properties.is_muc_pm:
            return properties.jid
        return properties.jid.new_as_bare()

    def _parse_if_private_message(
        self, stanza: Message, properties: MessageProperties
    ) -> None:
        muc_user = stanza.getTag("x", namespace=Namespace.MUC_USER)
        if muc_user is None:
            return

        if not properties.jid.is_full:
            return

        if properties.type.is_chat or (
            properties.type.is_error and not muc_user.getChildren()
        ):
            properties.muc_private_message = True

    def _process_message_after_base(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        # This handler runs after decryption, when handlers had the chance
        # to decrypt the body

        fallbacks_for = parse_fallback_indication(self._log, stanza)

        properties.body = stanza.getBody()
        properties.bodies = BodyData(
            stanza, fallbacks_for, self._client.get_supported_fallback_ns()
        )
        properties.thread = stanza.getThread()
        properties.subject = stanza.getSubject()
        forms = stanza.getTags("x", namespace=Namespace.DATA)
        if forms:
            properties.forms = forms

        xhtml = stanza.getXHTML()
        if xhtml is None:
            return

        if xhtml.getTag("body", namespace=Namespace.XHTML) is None:
            self._log.warning("xhtml without body found")
            self._log.warning(stanza)
            return

        properties.xhtml = XHTMLData(xhtml)

    def _parse_type(self, stanza: Message) -> MessageType:
        type_ = stanza.getType()
        if type_ is None:
            return MessageType.NORMAL

        try:
            return MessageType(type_)
        except ValueError:
            self._log.warning("Message with invalid type: %s", type_)
            self._log.warning(stanza)
            raise NodeProcessed

    @staticmethod
    def _parse_self_message(stanza: Message, properties: MessageProperties) -> bool:
        if properties.type.is_groupchat:
            return False
        return stanza.getFrom().bare_match(stanza.getTo())

    def _parse_stanza_ids(self, stanza: Message) -> list[StanzaIDData]:
        stanza_ids: list[StanzaIDData] = []
        for stanza_id in stanza.getTags("stanza-id", namespace=Namespace.SID):
            id_ = stanza_id.getAttr("id")
            by = stanza_id.getAttr("by")
            if not id_ or not by:
                self._log.warning("Missing attributes on stanza-id")
                self._log.warning(stanza)
                continue

            stanza_ids.append(StanzaIDData(id=id_, by=by))

        return stanza_ids
