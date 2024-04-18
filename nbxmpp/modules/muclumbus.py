# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
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

import json

from nbxmpp.const import AnonymityMode
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.modules.util import finalize
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Node
from nbxmpp.structs import MuclumbusItem
from nbxmpp.structs import MuclumbusResult
from nbxmpp.task import http_request_task
from nbxmpp.task import iq_request_task

# API Documentation
# https://search.jabber.network/docs/api

class Muclumbus(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def request_parameters(self, jid):
        task = yield

        response = yield _make_parameter_request(jid)
        if response.isError():
            raise StanzaError(response)

        search = response.getTag('search', namespace=Namespace.MUCLUMBUS)
        if search is None:
            raise MalformedStanzaError('search node missing', response)

        dataform = search.getTag('x', namespace=Namespace.DATA)
        if dataform is None:
            raise MalformedStanzaError('dataform node missing', response)

        self._log.info('Muclumbus parameters received')
        yield finalize(task, extend_form(node=dataform))

    @iq_request_task
    def set_search(self, jid, dataform, items_per_page=50, after=None):
        _task = yield

        response = yield _make_search_query(jid,
                                            dataform,
                                            items_per_page,
                                            after)
        if response.isError():
            raise StanzaError(response)

        result = response.getTag('result', namespace=Namespace.MUCLUMBUS)
        if result is None:
            raise MalformedStanzaError('result node missing', response)

        items = result.getTags('item')
        if not items:
            yield MuclumbusResult(first=None,
                                  last=None,
                                  max=None,
                                  end=True,
                                  items=[])

        set_ = result.getTag('set', namespace=Namespace.RSM)
        if set_ is None:
            raise MalformedStanzaError('set node missing', response)

        first = set_.getTagData('first')
        last = set_.getTagData('last')
        try:
            max_ = int(set_.getTagData('max'))
        except Exception:
            raise MalformedStanzaError('invalid max value', response)

        results = []
        for item in items:
            jid = item.getAttr('address')
            name = item.getTagData('name')
            nusers = item.getTagData('nusers')
            description = item.getTagData('description')
            language = item.getTagData('language')
            is_open = item.getTag('is-open') is not None

            try:
                anonymity_mode = AnonymityMode(
                    item.getTagData('anonymity-mode'))
            except ValueError:
                anonymity_mode = AnonymityMode.UNKNOWN
            results.append(MuclumbusItem(jid=jid,
                                         name=name or '',
                                         nusers=nusers or '',
                                         description=description or '',
                                         language=language or '',
                                         is_open=is_open,
                                         anonymity_mode=anonymity_mode))
        yield MuclumbusResult(first=first,
                              last=last,
                              max=max_,
                              end=len(items) < max_,
                              items=results)

    @http_request_task
    def set_http_search(self, uri, keywords, after=None):
        _task = yield

        search = {'keywords': keywords}
        if after is not None:
            search['after'] = after

        body = json.dumps(search).encode()

        session = self._client.http_session
        request = session.create_request()
        request.set_request_body('application/json', body)
        request.send('POST', uri)

        request = yield request

        if not request.is_complete():
            self._log.warning(request.get_error_string())
            yield MuclumbusResult(first=None,
                                  last=None,
                                  max=None,
                                  end=True,
                                  items=[])

        response_body = request.get_data()
        response = json.loads(response_body)

        result = response['result']
        items = result.get('items')
        if items is None:
            yield MuclumbusResult(first=None,
                                  last=None,
                                  max=None,
                                  end=True,
                                  items=[])

        results = []
        for item in items:
            try:
                anonymity_mode = AnonymityMode(item['anonymity_mode'])
            except (ValueError, KeyError):
                anonymity_mode = AnonymityMode.UNKNOWN

            results.append(
                MuclumbusItem(jid=item['address'],
                              name=item['name'] or '',
                              nusers=str(item['nusers'] or ''),
                              description=item['description'] or '',
                              language=item['language'] or '',
                              is_open=item['is_open'],
                              anonymity_mode=anonymity_mode))

        yield MuclumbusResult(first=None,
                              last=result['last'],
                              max=None,
                              end=not result['more'],
                              items=results)


def _make_parameter_request(jid):
    query = Iq(to=jid, typ='get')
    query.addChild(node=Node('search',
                             attrs={'xmlns': Namespace.MUCLUMBUS}))
    return query


def _make_search_query(jid, dataform, items_per_page=50, after=None):
    search = Node('search', attrs={'xmlns': Namespace.MUCLUMBUS})
    search.addChild(node=dataform)
    rsm = search.addChild('set', namespace=Namespace.RSM)
    rsm.addChild('max').setData(items_per_page)
    if after is not None:
        rsm.addChild('after').setData(after)
    query = Iq(to=jid, typ='get')
    query.addChild(node=search)
    return query
