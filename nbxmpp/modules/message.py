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

from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import ErrorProperties
from nbxmpp.structs import StanzaIDData
from nbxmpp.const import MessageType

log = logging.getLogger('nbxmpp.m.message')


class BaseMessage:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_base,
                          priority=5),
            StanzaHandler(name='message',
                          callback=self._process_message_after_base,
                          priority=10),
        ]

    def _process_message_base(self, _con, stanza, properties):
        properties.type = self._parse_type(stanza)
        properties.jid = stanza.getFrom()
        properties.id = stanza.getID()
        properties.self_message = self._parse_self_message(stanza, properties)

        # Stanza ID
        id_, by = stanza.getStanzaIDAttrs()
        properties.stanza_id = StanzaIDData(id=id_, by=by)

        if properties.type.is_error:
            properties.error = ErrorProperties(stanza)

    @staticmethod
    def _process_message_after_base(_con, stanza, properties):
        # This handler runs after decryption handlers had the chance
        # to decrypt the body
        properties.body = stanza.getBody()
        properties.thread = stanza.getThread()
        properties.subject = stanza.getSubject()

    @staticmethod
    def _parse_type(stanza):
        type_ = stanza.getType()
        if type_ is None:
            return MessageType.NORMAL

        try:
            return MessageType(type_)
        except ValueError:
            log.warning('Message with invalid type: %s', type_)
            log.warning(stanza)
            raise NodeProcessed

    @staticmethod
    def _parse_self_message(stanza, properties):
        if properties.type.is_groupchat:
            return False
        return stanza.getFrom().bareMatch(stanza.getTo())
