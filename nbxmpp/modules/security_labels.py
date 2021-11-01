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
from typing import Dict
from typing import Optional

from dataclasses import dataclass

from nbxmpp import types
from nbxmpp.client import Client
from nbxmpp.jid import JID
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.errors import StanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.modules.base import BaseModule
from nbxmpp.builder import E
from nbxmpp.builder import Iq


class SecurityLabels(BaseModule):
    def __init__(self, client: Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_security_label,
                          ns=Namespace.SECLABEL,
                          priority=15),
        ]

    def _process_message_security_label(self,
                                        _client: Client,
                                        stanza: types.Message,
                                        properties: Any):

        security = stanza.find_tag('securitylabel', namespace=Namespace.SECLABEL)
        if security is None:
            return

        try:
            security_label = SecurityLabel.from_node(security)
        except ValueError as error:
            self._log.warning(error)
            return

        properties.security_label = security_label

    @iq_request_task
    def request_catalog(self, jid: JID):
        response = yield _make_catalog_request(self._client.domain, jid)
        if response.is_error():
            raise StanzaError(response)

        catalog_node = response.find_tag('catalog',
                                         namespace=Namespace.SECLABEL_CATALOG)
        to = catalog_node.get('to')
        items = catalog_node.find_tags('item')

        labels = {}
        default = None
        for item in items:
            label = item.get('selector')
            if label is None:
                continue

            security = item.find_tag('securitylabel',
                                     namespace=Namespace.SECLABEL)
            if security is None:
                continue

            try:
                security_label = SecurityLabel.from_node(security)
            except ValueError:
                continue

            labels[label] = security_label

            if item.get('default') == 'true':
                default = label

        yield Catalog(labels=labels, default=default)


def _make_catalog_request(domain: str, jid: JID) -> types.Iq:
    iq = Iq(to=domain)
    iq.add_tag('catalog', namespace=Namespace.SECLABEL_CATALOG, to=str(jid))
    return iq


@dataclass
class Displaymarking:
    name: str
    fgcolor: str
    bgcolor: str

    def to_node(self):
        displaymarking = E('displaymarking', namespace=Namespace.SECLABEL)
        if self.fgcolor and self.fgcolor != '#000':
            displaymarking.set('fgcolor', self.fgcolor)

        if self.bgcolor and self.bgcolor != '#FFF':
            displaymarking.set('bgcolor', self.bgcolor)

        if self.name:
            displaymarking.text = self.name

        return displaymarking

    @classmethod
    def from_node(cls, element: types.Base):
        return cls(name=element.text or '',
                   fgcolor=element.get('fgcolor') or '#000',
                   bgcolor=element.get('bgcolor') or '#FFF')


@dataclass
class SecurityLabel:
    displaymarking: Optional[Displaymarking]
    label: types.Base

    def to_node(self):
        security = E('securitylabel', namespace=Namespace.SECLABEL)
        if self.displaymarking is not None:
            security.append(self.displaymarking.to_node())

        security.append(self.label)
        return security

    @classmethod
    def from_node(cls, security: types.Base) -> SecurityLabel:
        displaymarking = security.find_tag('displaymarking')
        if displaymarking is not None:
            displaymarking = Displaymarking.from_node(displaymarking)

        label = security.find_tag('label')
        if label is None:
            raise ValueError('label node missing')

        return cls(displaymarking=displaymarking, label=label)


@dataclass
class Catalog:
    labels: Dict[str, SecurityLabel]
    default: str

    def get_label_names(self):
        return list(self.labels.keys())
