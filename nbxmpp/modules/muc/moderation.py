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

# XEP-0425: Message Moderation

from typing import Optional

from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response

from nbxmpp import JID
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import ModerationData
from nbxmpp.simplexml import Node
from nbxmpp.task import iq_request_task


class Moderation(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message,
                          typ='groupchat',
                          ns=Namespace.FASTEN,
                          priority=20),
        ]

    @iq_request_task
    def send_retract_request(self, muc_jid: JID, stanza_id: str,
                             reason: Optional[str] = None):
        _task = yield

        response = yield _make_retract_request(muc_jid, stanza_id, reason)

        yield process_response(response)

    @staticmethod
    def _process_message(_client, stanza: Node,
                        properties: MessageProperties) -> None:
        if not properties.jid.is_bare:
            return

        apply_to = stanza.getTag(
            'apply-to', namespace=Namespace.FASTEN)
        if apply_to is None:
            return

        moderated = apply_to.getTag(
            'moderated', namespace=Namespace.MESSAGE_MODERATE)
        if moderated is None:
            return

        retract = moderated.getTag(
                'retract', namespace=Namespace.MESSAGE_RETRACT)
        if retract is None:
            # Tag can be 'retract' or 'retracted', depending on whether the
            # server applies a tombstone for MAM messages or not.
            retract = moderated.getTag(
                'retracted', namespace=Namespace.MESSAGE_RETRACT)
        if retract is None:
            return

        properties.moderation = ModerationData(
            stanza_id=apply_to.getAttr('id'),
            moderator_jid=moderated.getAttr('by'),
            reason=moderated.getTagData('reason'),
            timestamp=retract.getAttr('stamp'))


def _make_retract_request(muc_jid: JID, stanza_id: str,
                          reason: Optional[str]) -> Iq:
    iq = Iq('set', Namespace.FASTEN, to=muc_jid)
    query = iq.setQuery(name='apply-to')
    query.setAttr('id', stanza_id)
    moderate = query.addChild(name='moderate',
                              namespace=Namespace.MESSAGE_MODERATE)
    moderate.addChild(name='retract', namespace=Namespace.MESSAGE_RETRACT)
    if reason is not None:
        moderate.addChild(name='reason', payload=[reason])
    return iq
