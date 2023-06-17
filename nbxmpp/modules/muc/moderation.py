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

from nbxmpp import JID
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import ModerationData
from nbxmpp.simplexml import Node
from nbxmpp.task import iq_request_task
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.modules.util import process_response


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
            StanzaHandler(name='message',
                          callback=self._process_message_moderated_tombstone,
                          typ='groupchat',
                          ns=Namespace.MESSAGE_MODERATE,
                          priority=20),
        ]

    @iq_request_task
    def send_retract_request(self, muc_jid: JID, stanza_id: str,
                             reason: Optional[str] = None):
        _task = yield

        response = yield _make_retract_request(muc_jid, stanza_id, reason)

        yield process_response(response)

    def _process_message_moderated_tombstone(
        self,
        _client,
        stanza: Node,
        properties: MessageProperties
    ) -> None:

        if not properties.is_mam_message:
            return

        moderated = stanza.getTag(
            'moderated', namespace=Namespace.MESSAGE_MODERATE)
        if moderated is None:
            return

        properties.moderation = self._parse_moderated(
            moderated, properties, properties.mam.id)

    def _process_message(self,
                         _client,
                         stanza: Node,
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

        stanza_id = apply_to.getAttr('id')
        if stanza_id is None:
            self._log.warning('apply-to element without stanza-id')
            self._log.warning(stanza)
            raise NodeProcessed

        properties.moderation = self._parse_moderated(moderated, properties, stanza_id)

    def _parse_moderated(
        self,
        moderated: Node,
        properties: MessageProperties,
        stanza_id: str
    ) -> ModerationData | None:

        retract, is_tombstone = _get_retract_element(moderated, properties)
        if retract is None:
            self._log.warning('Failed to find <retract/ed> element')
            return None

        try:
            by = _parse_by_attr(moderated)
        except ValueError as error:
            self._log.warning(error)
            by = None

        stamp = _parse_moderation_timestamp(retract, is_tombstone, properties)

        occupant_id = moderated.getTagAttr('occupant-id',
                                           'id',
                                           namespace=Namespace.OCCUPANT_ID)

        return ModerationData(
            stanza_id=stanza_id,
            moderator_jid=str(by),
            by=by,
            occupant_id=occupant_id,
            reason=moderated.getTagData('reason'),
            timestamp=retract.getAttr('stamp'),
            stamp=stamp,
            is_tombstone=is_tombstone)


def _get_retract_element(
    moderated: Node,
    properties: MessageProperties
) -> tuple[Node | None, bool]:

    retract = moderated.getTag(
            'retract', namespace=Namespace.MESSAGE_RETRACT)
    if retract is not None:
        return retract, False

    retracted = moderated.getTag(
        'retracted', namespace=Namespace.MESSAGE_RETRACT)
    if retracted is not None:
        return retracted, True and properties.is_mam_message
    return None, False


def _parse_by_attr(moderated: Node) -> JID | None:
    by_attr = moderated.getAttr('by')
    if by_attr is None:
        return None

    try:
        return JID.from_string(by_attr)
    except Exception as error:
        raise ValueError('Invalid JID: %s, %s' % (by_attr, error))


def _parse_moderation_timestamp(
    retract: Node,
    is_tombstone: bool,
    properties: MessageProperties
) -> float:

    if is_tombstone:
        stamp_attr = retract.getAttr('stamp')
        stamp = parse_datetime(
            stamp_attr, check_utc=True, convert='utc', epoch=True)
        if stamp is not None:
            return stamp

    if properties.is_mam_message:
        return properties.mam.timestamp

    return properties.timestamp


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
