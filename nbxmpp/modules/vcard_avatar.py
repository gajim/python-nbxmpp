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

from nbxmpp.protocol import NS_VCARD_UPDATE
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import PresenceType
from nbxmpp.const import AvatarState

log = logging.getLogger('nbxmpp.m.vcard_avatar')


class VCardAvatar:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._process_avatar,
                          ns=NS_VCARD_UPDATE,
                          priority=15)
        ]

    @staticmethod
    def _process_avatar(_con, stanza, properties):
        if properties.type != PresenceType.AVAILABLE:
            return

        update = stanza.getTag('x', namespace=NS_VCARD_UPDATE)
        if update is None:
            return

        avatar_sha = update.getTagData('photo')
        if avatar_sha is None:
            properties.avatar_state = AvatarState.NOT_READY
            log.info('%s is not ready to promote an avatar', stanza.getFrom())
            # Empty update element, ignore
            return

        if avatar_sha == '':
            properties.avatar_state = AvatarState.EMPTY
            log.info('%s empty avatar advertised', stanza.getFrom())
            return

        properties.avatar_sha = avatar_sha
        properties.avatar_state = AvatarState.ADVERTISED
        log.info('%s advertises %s', stanza.getFrom(), avatar_sha)
