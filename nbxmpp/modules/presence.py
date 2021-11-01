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
from typing import Union

from nbxmpp import builder
from nbxmpp import types
from nbxmpp.const import ErrorCondition
from nbxmpp.const import ErrorType
from nbxmpp.const import PresenceShow
from nbxmpp.const import PresenceType
from nbxmpp.elements import Stanza
from nbxmpp.lookups import register_class_lookup
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import log_calls
from nbxmpp.namespaces import Namespace
from nbxmpp.jid import JID
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import error_factory



class BasePresence(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._process_presence_base,
                          priority=10),
        ]

    def _process_presence_base(self,
                               _client: types.Client,
                               presence: types.Presence,
                               properties: Any):

        properties.type = self._parse_type(presence)
        properties.priority = self._parse_priority(presence)
        properties.show = self._parse_show(presence)
        properties.jid = presence.get_from()
        properties.id = presence.get('id')
        properties.status = presence.get_status() or ''

        if properties.type.is_error:
            properties.error = error_factory(presence)

        own_jid = self._client.get_bound_jid()
        properties.self_presence = own_jid == properties.jid
        properties.self_bare = properties.jid.bare_match(own_jid)

    def _parse_priority(self, presence: types.Presence) -> int:
        priority = presence.get_priority()
        if priority is None:
            return 0

        try:
            priority = int(priority)
        except Exception:
            self._log.warning('Invalid priority value: %s', priority)
            self._log.warning(presence)
            return 0

        if priority not in range(-128, 128):
            self._log.warning('Invalid priority value: %s', priority)
            self._log.warning(presence)
            return 0

        return priority

    def _parse_type(self, presence: types.Presence) -> PresenceType:
        type_ = presence.get('type')
        try:
            return PresenceType(type_)
        except ValueError:
            self._log.warning('Presence with invalid type received')
            self._log.warning(presence)
            error = presence.make_error(ErrorType.CANCEL,
                                        ErrorCondition.BAD_REQUEST,
                                        Namespace.XMPP_STANZAS)
            self._client.send_stanza(error)
            raise NodeProcessed

    def _parse_show(self, presence: types.Presence) -> PresenceShow:
        show = presence.get_show()
        if show is None:
            return PresenceShow.ONLINE
        try:
            return PresenceShow(show)
        except ValueError:
            self._log.warning('Presence with invalid show')
            self._log.warning(presence)
            return PresenceShow.ONLINE

    @log_calls
    def unsubscribe(self, to: Union[str, JID]):
        self._client.send_stanza(builder.Presence(to=to, type='unsubscribe'))

    @log_calls
    def unsubscribed(self, to: Union[str, JID]):
        self._client.send_stanza(builder.Presence(to=to, type='unsubscribed'))

    @log_calls
    def subscribed(self, to: Union[str, JID]):
        self._client.send_stanza(builder.Presence(to=to, type='subscribed'))

    @log_calls
    def subscribe(self,
                  to: Union[str, JID],
                  status: Optional[str] = None,
                  nickname: Optional[str] = None):

        self._client.send_stanza(builder.Presence(to=to,
                                                  type='subscribe',
                                                  status=status,
                                                  nickname=nickname))


class Presence(Stanza):
    
    def get_priority(self) -> Optional[str]:
        return self.find_tag_text('priority')

    def get_show(self) -> Optional[str]:
        return self.find_tag_text('show')
    
    def get_status(self) -> Optional[str]:
        return self.find_tag_text('status')
    


register_class_lookup('presence', Namespace.CLIENT, Presence)
