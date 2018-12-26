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
from nbxmpp.protocol import NS_CONFERENCE
from nbxmpp.protocol import JID
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import InviteType
from nbxmpp.const import MessageType
from nbxmpp.const import StatusCode
from nbxmpp.structs import DeclineData
from nbxmpp.structs import InviteData

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
                          callback=self._process_mediated_invite,
                          typ='normal',
                          ns=NS_MUC_USER,
                          priority=11),
            StanzaHandler(name='message',
                          callback=self._process_direct_invite,
                          typ='normal',
                          ns=NS_CONFERENCE,
                          priority=11),
            StanzaHandler(name='message',
                          callback=self._process_message,
                          ns=NS_MUC_USER,
                          priority=12),
        ]

    @staticmethod
    def _process_muc_presence(_con, stanza, properties):
        muc = stanza.getTag('x', namespace=NS_MUC)
        if muc is None:
            return
        properties.from_muc = True

    @staticmethod
    def _process_muc_user_presence(_con, stanza, properties):
        muc = stanza.getTag('x', namespace=NS_MUC_USER)
        if muc is None:
            return
        properties.from_muc = True

    @staticmethod
    def _process_groupchat_message(_con, _stanza, properties):
        properties.from_muc = True
        properties.muc_nickname = properties.jid.getResource() or None

    @staticmethod
    def _process_message(_con, stanza, properties):
        muc_user = stanza.getTag('x', namespace=NS_MUC_USER)
        if muc_user is None:
            return

        # MUC Private message
        if properties.type == MessageType.CHAT:
            properties.muc_private_message = True
            return

        if properties.is_muc_invite_or_decline:
            return

        properties.from_muc = True

        if not properties.jid.isBare:
            return

        # MUC Config change
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

    @staticmethod
    def _process_direct_invite(_con, stanza, properties):
        direct = stanza.getTag('x', namespace=NS_CONFERENCE)
        if direct is None:
            return

        muc_jid = direct.getAttr('jid')
        if muc_jid is None:
            # Not a direct invite
            # See https://xmpp.org/extensions/xep-0045.html#example-57
            # read implementation notes
            return

        data = {}
        data['muc'] = JID(muc_jid)
        data['from_'] = properties.jid
        data['reason'] = direct.getAttr('reason')
        data['password'] = direct.getAttr('password')
        data['continued'] = direct.getAttr('continue') == 'true'
        data['thread'] = direct.getAttr('thread')
        data['type'] = InviteType.DIRECT
        properties.muc_invite = InviteData(**data)

    @staticmethod
    def _process_mediated_invite(_con, stanza, properties):
        muc_user = stanza.getTag('x', namespace=NS_MUC_USER)
        if muc_user is None:
            return

        if properties.type != MessageType.NORMAL:
            return

        properties.from_muc = True

        data = {}

        invite = muc_user.getTag('invite')
        if invite is not None:
            data['muc'] = JID(properties.jid.getBare())
            data['from_'] = JID(invite.getAttr('from'))
            data['reason'] = invite.getTagData('reason')
            data['password'] = muc_user.getTagData('password')
            data['type'] = InviteType.MEDIATED

            data['continued'] = False
            data['thread'] = None
            continue_ = invite.getTag('continue')
            if continue_ is not None:
                data['continued'] = True
                data['thread'] = continue_.getAttr('thread')
            properties.muc_invite = InviteData(**data)
            return

        decline = muc_user.getTag('decline')
        if decline is not None:
            data['muc'] = JID(properties.jid.getBare())
            data['from_'] = JID(decline.getAttr('from'))
            data['reason'] = decline.getTagData('reason')
            properties.muc_decline = DeclineData(**data)
            return
