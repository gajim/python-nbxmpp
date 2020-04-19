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

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Node
from nbxmpp.protocol import Iq
from nbxmpp.protocol import isResultNode
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import PubSubEventData
from nbxmpp.structs import CommonResult
from nbxmpp.structs import PubSubConfigResult
from nbxmpp.structs import PubSubPublishResult
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error
from nbxmpp.modules.base import BaseModule


class PubSub(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_base,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=15),
        ]

    def _process_pubsub_base(self, _client, stanza, properties):
        properties.pubsub = True
        event = stanza.getTag('event', namespace=Namespace.PUBSUB_EVENT)

        delete = event.getTag('delete')
        if delete is not None:
            node = delete.getAttr('node')
            properties.pubsub_event = PubSubEventData(
                node, deleted=True)
            return

        purge = event.getTag('purge')
        if purge is not None:
            node = purge.getAttr('node')
            properties.pubsub_event = PubSubEventData(node, purged=True)
            return

        items = event.getTag('items')
        if items is not None:
            node = items.getAttr('node')

            retract = items.getTag('retract')
            if retract is not None:
                id_ = retract.getAttr('id')
                properties.pubsub_event = PubSubEventData(
                    node, id_, retracted=True)
                return

            if len(items.getChildren()) != 1:
                self._log.warning('PubSub event with != 1 item')
                self._log.warning(stanza)
                return

            item = items.getTag('item')
            if item is None:
                self._log.warning('No item node found')
                self._log.warning(stanza)
                return
            id_ = item.getAttr('id')
            properties.pubsub_event = PubSubEventData(node, id_, item)

    @call_on_response('_publish_result_received')
    def publish(self, jid, node, item, id_=None, options=None):
        query = Iq('set', to=jid)
        pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB)
        publish = pubsub.addChild('publish', {'node': node})
        attrs = {}
        if id_ is not None:
            attrs = {'id': id_}
        publish.addChild('item', attrs, [item])
        if options:
            publish = pubsub.addChild('publish-options')
            publish.addChild(node=options)
        return query

    @callback
    def _publish_result_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.warning, stanza)

        jid = stanza.getFrom()
        pubsub = stanza.getTag('pubsub', namespace=Namespace.PUBSUB)
        if pubsub is None:
            # XEP-0060: IQ payload is not mandatory on result
            return PubSubPublishResult(jid, None, None)

        publish = pubsub.getTag('publish')
        if publish is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed')

        node = publish.getAttr('node')
        item = publish.getTag('item')
        if item is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed')

        id_ = item.getAttr('id')
        return PubSubPublishResult(jid, node, id_)

    @call_on_response('_default_response')
    def retract(self, jid, node, id_, notify=True):
        query = Iq('set', to=jid)
        pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB)
        attrs = {'node': node}
        if notify:
            attrs['notify'] = 'true'
        retract = pubsub.addChild('retract', attrs=attrs)
        retract.addChild('item', {'id': id_})
        return query

    @call_on_response('_default_response')
    def set_node_configuration(self, jid, node, form):
        self._log.info('Set configuration for %s %s', node, jid)
        query = Iq('set', to=jid)
        pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB_OWNER)
        configure = pubsub.addChild('configure', {'node': node})
        form.setAttr('type', 'submit')
        configure.addChild(node=form)
        return query

    @call_on_response('_node_configuration_received')
    def get_node_configuration(self, jid, node):
        self._log.info('Request node configuration')
        query = Iq('get', to=jid)
        pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB_OWNER)
        pubsub.addChild('configure', {'node': node})
        return query

    @callback
    def _node_configuration_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.warning, stanza)

        jid = stanza.getFrom()
        pubsub = stanza.getTag('pubsub', namespace=Namespace.PUBSUB_OWNER)
        if pubsub is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed',
                               'No pubsub node found')

        configure = pubsub.getTag('configure')
        if configure is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed',
                               'No configure node found')

        node = configure.getAttr('node')

        forms = configure.getTags('x', namespace=Namespace.DATA)
        for form in forms:
            dataform = extend_form(node=form)
            form_type = dataform.vars.get('FORM_TYPE')
            if form_type is None or form_type.value != Namespace.PUBSUB_CONFIG:
                continue
            self._log.info('Node configuration received from: %s', jid)
            return PubSubConfigResult(jid=jid, node=node, form=dataform)

        return raise_error(self._log.warning, stanza, 'stanza-malformed',
                           'No valid form type found')

    @callback
    def _default_response(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)
        return CommonResult(jid=stanza.getFrom())


def get_pubsub_request(jid, node, id_=None, max_items=None):
    query = Iq('get', to=jid)
    pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB)
    items = pubsub.addChild('items', {'node': node})
    if max_items is not None:
        items.setAttr('max_items', max_items)
    if id_ is not None:
        items.addChild('item', {'id': id_})
    return query


def get_pubsub_item(stanza):
    pubsub_node = stanza.getTag('pubsub')
    items_node = pubsub_node.getTag('items')
    return items_node.getTag('item')


def get_pubsub_items(stanza, node=None):
    pubsub_node = stanza.getTag('pubsub')
    items_node = pubsub_node.getTag('items')
    if node is not None and items_node.getAttr('node') != node:
        return None

    if items_node is not None:
        return items_node.getTags('item')
    return None


def get_publish_options(config):
    options = Node(Namespace.DATA + ' x', attrs={'type': 'submit'})
    field = options.addChild('field',
                             attrs={'var': 'FORM_TYPE', 'type': 'hidden'})
    field.setTagData('value', Namespace.PUBSUB_PUBLISH_OPTIONS)

    for var, value in config.items():
        field = options.addChild('field', attrs={'var': var})
        field.setTagData('value', value)
    return options
