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

from nbxmpp.protocol import NS_MUC_USER
from nbxmpp.protocol import NS_MUC
from nbxmpp.util import StanzaHandler
from nbxmpp.const import MessageType
from nbxmpp.const import StatusCode

log = logging.getLogger('nbxmpp.m.presence')


class MUC:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._process_muc_presence,
                          ns=NS_MUC,
                          priority=11),
            StanzaHandler(name='presence',
                          callback=self._process_muc_user_presence,
                          ns=NS_MUC_USER,
                          priority=11),
            StanzaHandler(name='message',
                          callback=self._process_groupchat_message,
                          typ='groupchat',
                          priority=11),
            StanzaHandler(name='message',
                          callback=self._process_message,
                          ns=NS_MUC_USER,
                          priority=11),
        ]

    def _process_muc_presence(self, _con, stanza, properties):
        muc = stanza.getTag('x', namespace=NS_MUC)
        if muc is None:
            return
        properties.from_muc = True

    def _process_muc_user_presence(self, _con, stanza, properties):
        muc = stanza.getTag('x', namespace=NS_MUC_USER)
        if muc is None:
            return
        properties.from_muc = True

    def _process_groupchat_message(self, _con, stanza, properties):
        properties.from_muc = True

    def _process_message(self, _con, stanza, properties):
        muc_user = stanza.getTag('x', namespace=NS_MUC_USER)
        if muc_user is None:
            return

        if properties.type == MessageType.CHAT:
            properties.muc_private_message = True
            return

        if not properties.jid.isBare:
            return

        properties.from_muc = True

        # https://xmpp.org/extensions/xep-0045.html#registrar-statuscodes
        message_status_codes = [
            StatusCode.SHOWING_UNAVAILABLE,
            StatusCode.NOT_SHOWING_UNAVAILABLE,
            StatusCode.CONFIG_NON_PRIVACY_RELATED,
            StatusCode.CONFIG_ROOM_LOGGING,
            StatusCode.CONFIG_NO_ROOM_LOGGING,
            StatusCode.CONFIG_NON_ANONYMOUS,
            StatusCode.CONFIG_SEMI_ANONYMOUS,
            StatusCode.CONFIG_FULL_ANONYMOUS
        ]

        codes = set()
        for status in muc_user.getTags('status'):
            try:
                code = StatusCode(status.getAttr('code'))
            except ValueError:
                log.warning('Received invalid status code: %s',
                            status.getAttr('code'))
                log.warning(stanza)
                continue
            if code in message_status_codes:
                codes.add(code)

        if codes:
            properties.muc_status_codes = codes
