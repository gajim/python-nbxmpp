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

from nbxmpp.const import AvatarState
from nbxmpp.const import PresenceType
from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Presence
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class VCardAvatar(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._process_avatar,
                          ns=Namespace.VCARD_UPDATE,
                          priority=15)
        ]

    def _process_avatar(self, _client: Client, stanza: Presence, properties: PresenceProperties) -> None:
        if properties.type != PresenceType.AVAILABLE:
            return

        update = stanza.getTag('x', namespace=Namespace.VCARD_UPDATE)
        if update is None:
            return

        avatar_sha = update.getTagData('photo')
        if avatar_sha is None:
            properties.avatar_state = AvatarState.NOT_READY
            self._log.info('%s is not ready to promote an avatar',
                           stanza.getFrom())
            # Empty update element, ignore
            return

        if avatar_sha == '':
            properties.avatar_state = AvatarState.EMPTY
            self._log.info('%s empty avatar advertised', stanza.getFrom())
            return

        properties.avatar_sha = avatar_sha
        properties.avatar_state = AvatarState.ADVERTISED
        self._log.info('%s advertises %s', stanza.getFrom(), avatar_sha)
