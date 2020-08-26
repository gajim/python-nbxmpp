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

from nbxmpp.protocol import NodeProcessed
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import StanzaIDData
from nbxmpp.structs import XHTMLData
from nbxmpp.util import error_factory
from nbxmpp.const import MessageType
from nbxmpp.modules.base import BaseModule


class BaseMessage(BaseModule):
    def __init__(self, client):
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

    def _process_message_base(self, _client, stanza, properties):
        properties.type = self._parse_type(stanza)

        # Determine remote JID
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

        properties.from_ = stanza.getFrom()
        properties.to = stanza.getTo()
        properties.id = stanza.getID()
        properties.self_message = self._parse_self_message(stanza, properties)

        # Stanza ID
        id_, by = stanza.getStanzaIDAttrs()
        if id_ is not None and by is not None:
            properties.stanza_id = StanzaIDData(id=id_, by=by)

        if properties.type.is_error:
            properties.error = error_factory(stanza)

    def _process_message_after_base(self, _client, stanza, properties):
        # This handler runs after decryption handlers had the chance
        # to decrypt the body
        properties.body = stanza.getBody()
        properties.thread = stanza.getThread()
        properties.subject = stanza.getSubject()
        forms = stanza.getTags('x', namespace=Namespace.DATA)
        if forms:
            properties.forms = forms

        xhtml = stanza.getXHTML()
        if xhtml is None:
            return

        if xhtml.getTag('body', namespace=Namespace.XHTML) is None:
            self._log.warning('xhtml without body found')
            self._log.warning(stanza)
            return

        properties.xhtml = XHTMLData(xhtml)

    def _parse_type(self, stanza):
        type_ = stanza.getType()
        if type_ is None:
            return MessageType.NORMAL

        try:
            return MessageType(type_)
        except ValueError:
            self._log.warning('Message with invalid type: %s', type_)
            self._log.warning(stanza)
            raise NodeProcessed

    @staticmethod
    def _parse_self_message(stanza, properties):
        if properties.type.is_groupchat:
            return False
        return stanza.getFrom().bare_match(stanza.getTo())
