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

from nbxmpp import types
from nbxmpp.const import ErrorCondition
from nbxmpp.const import ErrorType
from nbxmpp.const import IqType
from nbxmpp.elements import Stanza
from nbxmpp.elements import register_class_lookup
from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import error_factory
from nbxmpp import builder


class BaseIq(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._process_iq_base,
                          priority=10),
        ]

    def _process_iq_base(self, _client: types.Client, iq: types.Iq, properties: Any):

        try:
            properties.type = IqType(iq.get('type'))
        except ValueError:
            self._log.warning('invalid type: %s', iq.get('type'))
            self._log.warning(iq)
            self._client.send_stanza(
                iq.make_error(ErrorType.CANCEL,
                              ErrorCondition.BAD_REQUEST,
                              Namespace.XMPP_STANZAS))
            raise NodeProcessed

        properties.jid = iq.get_from()
        properties.id = iq.get('id')

        childs = iq.get_children()
        for child in childs:
            if child.localname != 'error':
                properties.payload = child
                break

        properties.query = iq.get_query()

        if properties.type.is_error:
            properties.error = error_factory(iq)


class Iq(Stanza):

    def is_error(self) -> bool: 
        return self.get('type') == 'error'

    def is_result(self) -> bool: 
        return self.get('type') == 'result'

    def get_query(self,
                  namespace: Optional[str] = None,
                  node: Optional[str] = None) -> Optional[types.Base]:

        if namespace is None:
            query = self.find('{*}query')
        else:
            query = self.find_tag('query', namespace=namespace)

        if query is None:
            return query

        if node is not None:
            if query.get('node') == node:
                return query
            return None

        return query

    def add_query(self,
                  namespace: Optional[str] = None,
                  node: Optional[str] = None) -> types.Base:
        query = self.add_tag('query', namespace=namespace)
        if node is not None:
            query.set('node', node)
        return query

    def make_result(self) -> types.Iq:
        return builder.Iq(to=self.get('from'),
                          type='result',
                          id=self.get('id'))


register_class_lookup('iq', Namespace.CLIENT, Iq)
