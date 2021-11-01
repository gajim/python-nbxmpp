# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
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

from typing import Any, Optional

import hashlib
from dataclasses import dataclass
from dataclasses import field

from nbxmpp import types
from nbxmpp.client import Client
from nbxmpp.jid import JID
from nbxmpp.task import iq_request_task
from nbxmpp.util import b64decode
from nbxmpp.util import b64encode
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.builder import Iq
from nbxmpp.builder import E
from nbxmpp.namespaces import Namespace
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response


class VCardTemp(BaseModule):
    def __init__(self, client: Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def request_vcard(self, jid: Optional[JID] = None):

        response = yield _make_vcard_request(jid)

        if response.is_error():
            raise StanzaError(response)

        vcard_node = _get_vcard_node(response)
        yield VCard.from_node(vcard_node)

    @iq_request_task
    def set_vcard(self, vcard: VCard, jid: Optional[JID] = None):

        response = yield _make_vcard_publish(jid, vcard)
        yield process_response(response)


def _make_vcard_request(jid: Optional[JID]) -> types.Iq:
    iq = Iq(to=jid)
    iq.add_tag('vCard', namespace=Namespace.VCARD)
    return iq


def _get_vcard_node(response: types.Iq) -> types.Base:
    vcard_node = response.find_tag('vCard', namespace=Namespace.VCARD)
    if vcard_node is None:
        raise MalformedStanzaError('vCard node missing', response)
    return vcard_node


def _make_vcard_publish(jid: Optional[JID], vcard: VCard) -> types.Iq:
    iq = Iq(to=jid, type='set')
    iq.append(vcard.to_node())
    return iq


@dataclass
class VCard:
    data: dict[Any, Any] = field(default_factory=dict)

    @classmethod
    def from_node(cls, element: types.Base) -> VCard:
        dict_: dict[Any, Any] = {}
        for info in element:
            name = info.localname
            if name in ('ADR', 'TEL', 'EMAIL'):
                dict_.setdefault(name, [])
                entry = {}
                for child in info:
                    entry[child.localname] = child.text or ''
                dict_[name].append(entry)
            elif not list(info):
                dict_[name] = info.text or ''
            else:
                dict_[name] = {}
                for child in info:
                    dict_[name][child.localname] = child.text or ''

        return cls(data=dict_)

    def to_node(self) -> types.Base:
        vcard = E('vCard', namespace=Namespace.VCARD)
        for i in self.data:
            if i == 'jid':
                continue
            if isinstance(self.data[i], dict):
                child = vcard.add_tag(i)
                for j in self.data[i]:
                    child.add_tag_text(j, self.data[i][j])
            elif isinstance(self.data[i], list):
                for j in self.data[i]:
                    child = vcard.add_tag(i)
                    for k in j:
                        child.add_tag_text(k, j[k])
            else:
                vcard.add_tag_text(i, self.data[i])
        return vcard

    def set_avatar(self, avatar: bytes, type_: Optional[str] = None):
        avatar_str = b64encode(avatar)
        if 'PHOTO' not in self.data:
            self.data['PHOTO'] = {}

        self.data['PHOTO']['BINVAL'] = avatar_str

        if type_ is not None:
            self.data['PHOTO']['TYPE'] = type_

    def get_avatar(self) -> tuple[Optional[bytes], Optional[str]]:
        try:
            avatar = self.data['PHOTO']['BINVAL']
        except Exception:
            return None, None

        if not avatar:
            return None, None

        avatar = b64decode(avatar)
        avatar_sha = hashlib.sha1(avatar).hexdigest()
        return avatar, avatar_sha
