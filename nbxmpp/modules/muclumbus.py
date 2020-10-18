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

from gi.repository import Soup

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Node
from nbxmpp.protocol import Iq
from nbxmpp.structs import MuclumbusItem
from nbxmpp.structs import MuclumbusResult
from nbxmpp.const import AnonymityMode
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.task import http_request_task
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize


# API Documentation
# https://search.jabber.network/docs/api

class Muclumbus(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

        self._proxy_resolver = None
        self._soup_session = Soup.Session()

    def set_proxy(self, proxy):
        if proxy is None:
            return
        self._proxy_resolver = proxy.get_resolver()
        self._soup_session.props.proxy_resolver = self._proxy_resolver

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

        message = Soup.Message.new('POST', uri)
        message.set_request('application/json',
                            Soup.MemoryUse.COPY,
                            json.dumps(search).encode())

        response_message = yield message

        soup_body = response_message.get_property('response-body')

        if response_message.status_code != 200:
            self._log.warning(soup_body.data)
            yield MuclumbusResult(first=None,
                                  last=None,
                                  max=None,
                                  end=True,
                                  items=[])

        response = json.loads(soup_body.data)

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
