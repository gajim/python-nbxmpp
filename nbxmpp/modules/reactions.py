# Copyright (C) 2022 Philipp Hörist <philipp AT hoerist.com>
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
import typing

from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import Reactions as ReactionStruct
from nbxmpp.structs import StanzaHandler

if typing.TYPE_CHECKING:
    from nbxmpp.client import Client
    from nbxmpp.protocol import Message


class Reactions(BaseModule):
    def __init__(self, client: 'Client'):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name='message',
                callback=self._process_message_reaction,
                ns=Namespace.REACTIONS,
                priority=15,
            ),
        ]

    def _process_message_reaction(
        self,
        _client: 'Client',
        stanza: 'Message',
        properties: MessageProperties
    ) -> None:
        reactions = stanza.getTag('reactions', namespace=Namespace.REACTIONS)

        if reactions is None:
            return

        id_ = reactions.getAttr('id')
        if not id_:
            self._log.warning('Reactions without ID')
            return

        emojis: set[str] = set()
        for reaction in reactions.getTags('reaction'):
            # we strip for clients that might add white spaces and/or
            # new lines in the reaction content.
            emoji = reaction.getData().strip()
            if emoji:
                emojis.add(emoji)
            else:
                self._log.warning('Empty reaction')
                self._log.warning(stanza)

        properties.reactions = ReactionStruct(id_, emojis)
