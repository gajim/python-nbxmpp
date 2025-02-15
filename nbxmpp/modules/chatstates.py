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

from typing import TYPE_CHECKING

from nbxmpp.const import Chatstate
from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Chatstates(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_message_chatstate,
                ns=Namespace.CHATSTATES,
                priority=15,
            ),
        ]

    def _process_message_chatstate(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        try:
            chatstate = parse_chatstate(stanza)
        except ValueError as error:
            self._log.warning("Invalid chatstate: %s", error)
            self._log.warning(stanza)
            return

        if chatstate is None:
            return

        if properties.is_mam_message:
            return

        properties.chatstate = chatstate


def parse_chatstate(stanza: Message) -> Chatstate | None:
    children = stanza.getChildren()
    for child in children:
        if child.getNamespace() == Namespace.CHATSTATES:
            return Chatstate(child.getName())
    return None
