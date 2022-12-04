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

# XEP-0461: Message Replies

from __future__ import annotations

from typing import Optional
from typing import TYPE_CHECKING

from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import ReplyData
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Replies(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message,
                          ns=Namespace.REPLY,
                          priority=15)
        ]

    def _process_message(self,
                         _client: Client,
                         stanza: Message,
                         properties: MessageProperties
                         ) -> None:

        reply = stanza.getTag('reply', namespace=Namespace.REPLY)
        if reply is None:
            return

        reply_to = reply.getAttr('to')
        if reply_to is None:
            self._log.warning('Received reply without "to" attribute')
            return

        reply_to_id = reply.getAttr('id')
        if reply_to_id is None:
            self._log.warning('Received reply without "id"')
            return

        fallback_start, fallback_end = None, None
        fallback_data = self._get_fallback_data(stanza)
        if fallback_data is not None:
            fallback_start, fallback_end = fallback_data

        properties.reply_data = ReplyData(
            to=reply_to,
            id=reply_to_id,
            fallback_start=fallback_start,
            fallback_end=fallback_end)

    def _get_fallback_data(self, stanza: Message) -> Optional[tuple[int, int]]:
        fallback = stanza.getTag('fallback', namespace=Namespace.FALLBACK)
        if fallback is None or fallback.getAttr('for') != Namespace.REPLY:
            return None

        fallback_data = fallback.getTag('body')
        if fallback_data is None:
            return None

        start = fallback_data.getAttr('start')
        end = fallback_data.getAttr('end')
        if start is None or end is None:
            return None

        try:
            start = int(start)
            end = int(end)
        except ValueError:
            self._log.warning('Could not get fallback start/end')
            return None

        return start, end
