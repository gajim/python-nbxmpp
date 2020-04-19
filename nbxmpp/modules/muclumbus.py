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

from nbxmpp.protocol import NS_MUCLUMBUS
from nbxmpp.protocol import NS_DATA
from nbxmpp.protocol import NS_RSM
from nbxmpp.protocol import Node
from nbxmpp.protocol import Iq
from nbxmpp.protocol import isResultNode
from nbxmpp.structs import MuclumbusItem
from nbxmpp.structs import MuclumbusResult
from nbxmpp.const import AnonymityMode
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error
from nbxmpp.modules.base import BaseModule


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

    @call_on_response('_parameters_received')
    def request_parameters(self, jid):
        query = Iq(to=jid, typ='get')
        query.addChild(node=Node('search', attrs={'xmlns': NS_MUCLUMBUS}))
        return query

    @callback
    def _parameters_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)

        search = stanza.getTag('search', namespace=NS_MUCLUMBUS)
        if search is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed')

        dataform = search.getTag('x', namespace=NS_DATA)
        if dataform is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed')

        self._log.info('Muclumbus parameters received')
        return extend_form(node=dataform)

    @call_on_response('_search_received')
    def set_search(self, jid, dataform, items_per_page=50, after=None):
        search = Node('search', attrs={'xmlns': NS_MUCLUMBUS})
        search.addChild(node=dataform)
        rsm = search.addChild('set', namespace=NS_RSM)
        rsm.addChild('max').setData(items_per_page)
        if after is not None:
            rsm.addChild('after').setData(after)
        query = Iq(to=jid, typ='get')
        query.addChild(node=search)
        return query

    def set_http_search(self, uri, keywords, after=None,
                        callback=None, user_data=None):
        search = {'keywords': keywords}
        if after is not None:
            search['after'] = after

        message = Soup.Message.new('POST', uri)
        message.set_request('application/json',
                            Soup.MemoryUse.COPY,
                            json.dumps(search).encode())

        self._soup_session.queue_message(message,
                                         self._http_search_received,
                                         callback,
                                         user_data)

    @callback
    def _search_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)

        result = stanza.getTag('result', namespace=NS_MUCLUMBUS)
        if result is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed')

        items = result.getTags('item')
        if not items:
            return MuclumbusResult(first=None,
                                   last=None,
                                   max=None,
                                   end=True,
                                   items=[])

        set_ = result.getTag('set', namespace=NS_RSM)
        if set_ is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed')

        first = set_.getTagData('first')
        last = set_.getTagData('last')
        try:
            max_ = int(set_.getTagData('max'))
        except Exception:
            return raise_error(self._log.warning, stanza, 'stanza-malformed')

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
        return MuclumbusResult(first=first,
                               last=last,
                               max=max_,
                               end=len(items) < max_,
                               items=results)

    def _http_search_received(self, _session, message, callback, user_data):

        def exec_callback(muclumbus_result):
            if user_data is None:
                callback(muclumbus_result)
            else:
                callback(muclumbus_result, user_data)

        soup_body = message.get_property('response-body')

        if message.status_code != 200:
            self._log.warning(soup_body.data)
            exec_callback(MuclumbusResult(first=None,
                                          last=None,
                                          max=None,
                                          end=True,
                                          items=[]))

        response = json.loads(soup_body.data)

        result = response['result']
        items = result.get('items')
        if items is None:
            exec_callback(MuclumbusResult(first=None,
                                          last=None,
                                          max=None,
                                          end=True,
                                          items=[]))

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

        exec_callback(MuclumbusResult(first=None,
                                      last=result['last'],
                                      max=None,
                                      end=not result['more'],
                                      items=results))
