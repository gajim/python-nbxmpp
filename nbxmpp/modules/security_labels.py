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

from typing import Dict

from dataclasses import dataclass

from nbxmpp.protocol import Iq
from nbxmpp.simplexml import Node
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.errors import StanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.modules.base import BaseModule


class SecurityLabels(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_security_label,
                          ns=Namespace.SECLABEL,
                          priority=15),
        ]

    def _process_message_security_label(self, _client, stanza, properties):
        security = stanza.getTag('securitylabel', namespace=Namespace.SECLABEL)
        if security is None:
            return

        try:
            security_label = SecurityLabel.from_node(security)
        except ValueError as error:
            self._log.warning(error)
            return

        properties.security_label = security_label

    @iq_request_task
    def request_catalog(self, jid):
        _task = yield

        response = yield _make_catalog_request(self._client.domain, jid)
        if response.isError():
            raise StanzaError(response)

        catalog_node = response.getTag('catalog',
                                       namespace=Namespace.SECLABEL_CATALOG)
        to = catalog_node.getAttr('to')
        items = catalog_node.getTags('item')

        labels = {}
        default = None
        for item in items:
            label = item.getAttr('selector')
            if label is None:
                continue

            security = item.getTag('securitylabel',
                                   namespace=Namespace.SECLABEL)
            if security is None:
                continue

            try:
                security_label = SecurityLabel.from_node(security)
            except ValueError:
                continue

            labels[label] = security_label

            if item.getAttr('default') == 'true':
                default = label

        yield Catalog(labels=labels, default=default)


def _make_catalog_request(domain, jid):
    iq = Iq(typ='get', to=domain)
    iq.addChild(name='catalog',
                namespace=Namespace.SECLABEL_CATALOG,
                attrs={'to': jid})
    return iq


@dataclass
class Displaymarking:
    name: str
    fgcolor: str
    bgcolor: str

    def to_node(self):
        displaymarking = Node(tag='displaymarking')
        if self.fgcolor and self.fgcolor != '#000':
            displaymarking.setAttr('fgcolor', self.fgcolor)

        if self.bgcolor and self.bgcolor != '#FFF':
            displaymarking.setAttr('bgcolor', self.bgcolor)

        if self.name:
            displaymarking.setData(self.name)

        return displaymarking

    @classmethod
    def from_node(cls, node):
        return cls(name=node.getData(),
                   fgcolor=node.getAttr('fgcolor') or '#000',
                   bgcolor=node.getAttr('bgcolor') or '#FFF')


@dataclass
class SecurityLabel:
    displaymarking: Displaymarking
    label: Node

    def to_node(self):
        security = Node(tag='securitylabel',
                        attrs={'xmlns': Namespace.SECLABEL})
        if self.displaymarking is not None:
            security.addChild(node=self.displaymarking.to_node())
        security.addChild(node=self.label)
        return security

    @classmethod
    def from_node(cls, security):
        displaymarking = security.getTag('displaymarking')
        if displaymarking is not None:
            displaymarking = Displaymarking.from_node(displaymarking)

        label = security.getTag('label')
        if label is None:
            raise ValueError('label node missing')

        return cls(displaymarking=displaymarking, label=label)


@dataclass
class Catalog:
    labels: Dict[str, SecurityLabel]
    default: str

    def get_label_names(self):
        return list(self.labels.keys())
