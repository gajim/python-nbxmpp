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

from typing import Optional
from typing import Union
from typing import cast

from lxml import etree
from nbxmpp.const import IqType, MessageType, PresenceType

from nbxmpp.lookups import ElementLookup
from nbxmpp.elements import Base
from nbxmpp.elements import StreamStart as _StreamStart
from nbxmpp.elements import StreamEnd as StreamEnd
from nbxmpp.elements import Open as _Open
from nbxmpp.elements import Close as _Close
from nbxmpp.elements import create_nsmap_and_tag
from nbxmpp.jid import JID
from nbxmpp.namespaces import Namespace
from nbxmpp import types


_element_parser = etree.XMLParser()
_element_parser.set_element_class_lookup(ElementLookup)


def E(tag: str,
      text: Optional[str] = None,
      namespace: Optional[str] = None,
      **attrib: str) -> Base:

    tag, nsmap = create_nsmap_and_tag(tag, namespace)

    element = cast(Base, _element_parser.makeelement(tag,
                                                     nsmap=nsmap,
                                                     attrib=attrib))
    if text is not None:
        element.text = text
    return element


def Message(to: Union[str, JID],
            type: Optional[str] = None,
            id: Optional[str] = None) -> types.Message:

    message = cast(types.Message, E('message', namespace='jabber:client'))

    if isinstance(to, str):
        to = JID.from_string(to)
    message.set_to(str(to))

    if type is not None:
        MessageType(type)
        message.set('type', type)

    if id is not None:
        message.set('id', id)

    return message


def Iq(to: Optional[Union[str, JID]] = None,
       type: Optional[str] = 'get',
       id: Optional[str] = None) -> types.Iq:

    iq = cast(types.Iq, E('iq', namespace='jabber:client'))

    IqType(type)
    iq.set('type', type)

    if isinstance(to, str):
        to = JID.from_string(to)
    iq.set_to(str(to))

    if id is not None:
        iq.set('id', id)

    return iq


def Presence(to: Optional[Union[str, JID]] = None,
             type: Optional[str] = None,
             id: Optional[str] = None,
             priority: Optional[int] = None,
             show: Optional[str] = None,
             status: Optional[str] = None,
             nickname: Optional[str] = None,
             idle_time: Optional[str] = None,
             signed: Optional[str] = None,
             muc_join: Optional[bool] = False,
             muc_history: Optional[str] = None,
             muc_password: Optional[str] = None,
             caps: Optional[dict[str, str]] = None) -> types.Presence:

    presence = cast(types.Presence, E('presence', namespace='jabber:client'))

    if type is not None:
        PresenceType(type)
        presence.set('type', type)

    if to is not None:
        if isinstance(to, str):
            to = JID.from_string(to)
        presence.set_to(str(to))

    if id is not None:
        presence.set('id', id)

    if priority is not None:
        if priority not in range(-128, 128):
            raise ValueError('invalid priority: %s' % priority)
        presence.add_tag_text('priority', str(priority))

    if show is not None:
        if show not in ('chat', 'away', 'xa', 'dnd'):
            raise ValueError('invalid show value: %s' % show)
        presence.add_tag_text('show', show)

    if status is not None:
        presence.add_tag_text('status', status)

    if caps is not None and type != 'unavailable':
        presence.add_tag('c', namespace=Namespace.CAPS, **caps)

    if nickname is not None:
        presence.add_tag_text('nick', nickname, namespace=Namespace.NICK)

    if idle_time is not None:
        presence.add_tag('idle', namespace=Namespace.IDLE, since=idle_time)

    if signed is not None:
        presence.add_tag_text('x', signed, namespace=Namespace.SIGNED)

    if muc_join or muc_history is not None or muc_password is not None:
        muc_x = presence.add_tag('x', namespace=Namespace.MUC)
        if muc_history is not None:
            muc_x.add_tag_text('history', muc_history)

        if muc_password is not None:
            muc_x.add_tag_text('password', muc_password)

    return presence


def DataForm(type: str) -> types.DataForm:
    dataform = E('x', namespace=Namespace.DATA)
    dataform.set_type(type)
    return dataform


def StreamStart(domain: str, lang: str) -> types.Base:
    return _StreamStart(attrib={'version': '1.0',
                                'to': domain,
                                f'{{{Namespace.XML}}}lang': lang},
                        nsmap={'stream': Namespace.STREAMS,
                               'xml': Namespace.XML,
                                None: Namespace.CLIENT})

def Open(domain: str, lang: str) -> types.Base:
    return _Open(attrib={'version': '1.0',
                         'to': domain,
                         f'{{{Namespace.XML}}}lang': lang},
                 nsmap={None: Namespace.FRAMING,
                        'xml': Namespace.XML})

def Close() -> types.Base:
    return _Close(nsmap={None: Namespace.FRAMING})


def parse(data: str) -> Base:
    return cast(Base, etree.fromstring(data, _element_parser))
