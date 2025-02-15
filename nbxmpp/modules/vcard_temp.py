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

from typing import TYPE_CHECKING

import hashlib
from dataclasses import dataclass
from dataclasses import field

from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.simplexml import Node
from nbxmpp.task import iq_request_task
from nbxmpp.util import b64decode
from nbxmpp.util import b64encode

if TYPE_CHECKING:
    from nbxmpp.client import Client


class VCardTemp(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def request_vcard(self, jid: JID | None = None):
        _task = yield

        response = yield _make_vcard_request(jid)

        if response.isError():
            raise StanzaError(response)

        vcard_node = _get_vcard_node(response)
        yield VCard.from_node(vcard_node)

    @iq_request_task
    def set_vcard(self, vcard: VCard, jid: JID | None = None):
        _task = yield

        response = yield _make_vcard_publish(jid, vcard)
        yield process_response(response)


def _make_vcard_request(jid: JID) -> Iq:
    iq = Iq(typ="get", to=jid)
    iq.addChild("vCard", namespace=Namespace.VCARD)
    return iq


def _get_vcard_node(response: Node) -> Node:
    vcard_node = response.getTag("vCard", namespace=Namespace.VCARD)
    if vcard_node is None:
        raise MalformedStanzaError("vCard node missing", response)
    return vcard_node


def _make_vcard_publish(jid: JID, vcard: VCard) -> Iq:
    iq = Iq(typ="set", to=jid)
    iq.addChild(node=vcard.to_node())
    return iq


@dataclass
class VCard:
    data: dict = field(default_factory=dict)

    @classmethod
    def from_node(cls, node: Node) -> VCard:
        dict_ = {}
        for info in node.getChildren():
            name = info.getName()
            if name in ("ADR", "TEL", "EMAIL"):
                dict_.setdefault(name, [])
                entry = {}
                for child in info.getChildren():
                    entry[child.getName()] = child.getData()
                dict_[name].append(entry)
            elif info.getChildren() == []:
                dict_[name] = info.getData()
            else:
                dict_[name] = {}
                for child in info.getChildren():
                    dict_[name][child.getName()] = child.getData()

        return cls(data=dict_)

    def to_node(self) -> Node:
        vcard = Node(tag="vCard", attrs={"xmlns": Namespace.VCARD})
        for i in self.data:
            if i == "jid":
                continue
            if isinstance(self.data[i], dict):
                child = vcard.addChild(i)
                for j in self.data[i]:
                    child.addChild(j).setData(self.data[i][j])
            elif isinstance(self.data[i], list):
                for j in self.data[i]:
                    child = vcard.addChild(i)
                    for k in j:
                        child.addChild(k).setData(j[k])
            else:
                vcard.addChild(i).setData(self.data[i])
        return vcard

    def set_avatar(self, avatar: bytes, type_: str | None = None) -> None:
        encoded_avatar = b64encode(avatar)
        if "PHOTO" not in self.data:
            self.data["PHOTO"] = {}

        self.data["PHOTO"]["BINVAL"] = encoded_avatar

        if type_ is not None:
            self.data["PHOTO"]["TYPE"] = type_

    def get_avatar(self) -> tuple[bytes | None, str | None]:
        try:
            avatar = self.data["PHOTO"]["BINVAL"]
        except Exception:
            return None, None

        if not avatar:
            return None, None

        encoded_avatar = b64decode(avatar)
        avatar_sha = hashlib.sha1(encoded_avatar).hexdigest()
        return encoded_avatar, avatar_sha
