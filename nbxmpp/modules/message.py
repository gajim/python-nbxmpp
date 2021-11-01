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
from typing import Optional

from nbxmpp import types
from nbxmpp.const import MessageType
from nbxmpp.elements import Base
from nbxmpp.elements import Stanza
from nbxmpp.lookups import register_class_lookup
from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import StanzaIDData
from nbxmpp.util import error_factory


class BaseMessage(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_base,
                          priority=5),
            StanzaHandler(name='message',
                          callback=self._process_message_after_base,
                          priority=10),
        ]

    def _process_message_base(self,
                              _client: types.Client,
                              message: types.Message,
                              properties: Any):

        properties.type = self._parse_type(message)

        # Determine remote JID
        if properties.is_carbon_message and properties.carbon.is_sent:
            properties.jid = message.get_to()

        elif properties.is_mam_message and not properties.type.is_groupchat:
            own_jid = self._client.get_bound_jid()
            if own_jid.bare_match(message.get_from()):
                properties.jid = message.get_to()
            else:
                properties.jid = message.get_from()

        else:
            properties.jid = message.get_from()

        properties.from_ = message.get_from()
        properties.to = message.get_to()
        properties.id = message.get('id')
        properties.self_message = self._parse_self_message(message, properties)

        # Stanza ID
        attrs = message.get_stanza_id_attrs()
        if attrs is not None:
            properties.stanza_id = StanzaIDData(attrs['id'], attrs['by'])

        if properties.type.is_error:
            properties.error = error_factory(message)

    def _process_message_after_base(self,
                                    _client: types.Client,
                                    message: types.Message,
                                    properties: Any):

        # This handler runs after decryption handlers had the chance
        # to decrypt the body

        properties.body = message.get_body()
        properties.thread = message.get_thread()
        properties.subject = message.get_subject()
        forms = message.find_tags('x', namespace=Namespace.DATA)
        if forms:
            properties.forms = forms

        xhtml = message.get_xhtml()
        if xhtml is None:
            return

        if xhtml.get_body() is None:
            self._log.warning('xhtml without body found')
            self._log.warning(message)
            return

        properties.xhtml = xhtml

    def _parse_type(self, message: types.Message) -> MessageType:
        type_ = message.get('type')
        if type_ is None:
            return MessageType.NORMAL

        try:
            return message.get_type()
        except ValueError:
            self._log.warning('Message with invalid type: %s', type_)
            self._log.warning(message)
            raise NodeProcessed

    @staticmethod
    def _parse_self_message(message: types.Message, properties: Any) -> bool:
        if properties.type.is_groupchat:
            return False
        return message.get_from().bare_match(message.get_to())



class Message(Stanza):

    def get_type(self) -> MessageType:
        type_ = self.get('type')
        if type_ is None:
            return MessageType.NORMAL
        return MessageType(type_)

    def get_body(self) -> Optional[str]:
        return self.find_tag_text('body')

    def get_thread(self) -> Optional[str]:
        return self.find_tag_text('thread')

    def get_subject(self) -> Optional[str]:
        return self.find_tag_text('subject')

    def get_xhtml(self) -> Optional[XHTML]:
        return self.find_tag('html', namespace=Namespace.XHTML_IM)

    def get_origin_id(self):
        return self.find_tag_attr('origin-id', 'id', namespace=Namespace.SID)

    def get_stanza_id_attrs(self) -> Optional[dict[str, str]]:
        stanza_id = self.find_tag('stanza-id', namespace=Namespace.SID)
        if stanza_id is None:
            return None
        return stanza_id.get_attribs()


class XHTML(Base):

    def get_body(self, pref_lang: Optional[str] = None) -> Optional[Base]:
        if pref_lang is not None:
            body = self._find_body_with_lang(pref_lang)
            if body is not None:
                return body

        body = self._find_body_with_lang('en')
        if body is not None:
            return body
        return self.find_tag('body', namespace=Namespace.XHTML)

    def _find_body_with_lang(self, lang: str) -> Optional[Base]:
        for body in self.find_tags('body', namespace=Namespace.XHTML):
            if lang == body.get(f'{Namespace.XML}lang'):
                return body


register_class_lookup('message', Namespace.CLIENT, Message)
register_class_lookup('html', Namespace.XHTML_IM, XHTML)
