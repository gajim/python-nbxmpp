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

from collections import namedtuple

from nbxmpp.task import iq_request_task
from nbxmpp.errors import is_error
from nbxmpp.errors import PubSubStanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import PubSubEventData
from nbxmpp.structs import CommonResult
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Node
from nbxmpp.namespaces import Namespace
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response
from nbxmpp.modules.util import raise_if_error
from nbxmpp.modules.util import finalize
from nbxmpp.modules.dataforms import extend_form


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

    @iq_request_task
    def request_item(self, node, id_, jid=None):
        task = yield

        response = yield _make_pubsub_request(node, id_=id_, jid=jid)

        if response.isError():
            raise PubSubStanzaError(response)

        item = _get_pubsub_item(response, node, id_)
        yield task.set_result(item)

    @iq_request_task
    def request_items(self, node, max_items=None, jid=None):
        _task = yield

        response = yield _make_pubsub_request(node,
                                              max_items=max_items,
                                              jid=jid)

        if response.isError():
            raise PubSubStanzaError(response)

        yield _get_pubsub_items(response, node)

    @iq_request_task
    def publish(self,
                node,
                item,
                id_=None,
                options=None,
                jid=None,
                force_node_options=False):

        _task = yield

        request = _make_publish_request(node, item, id_, options, jid)
        response = yield request

        if response.isError():
            error = PubSubStanzaError(response)
            if (not force_node_options or
                    error.app_condition != 'precondition-not-met'):
                raise error

            result = yield self.reconfigure_node(node, options, jid)
            if is_error(result):
                raise result

            response = yield request
            if response.isError():
                raise PubSubStanzaError(response)

        jid = response.getFrom()
        item_id = _get_published_item_id(response, node, id_)
        yield PubSubPublishResult(jid, node, item_id)

    @iq_request_task
    def get_access_model(self, node):
        _task = yield

        self._log.info('Request access model')

        result = yield self.get_node_configuration(node)

        raise_if_error(result)

        yield result.form['pubsub#access_model'].value

    @iq_request_task
    def set_access_model(self, node, model):
        task = yield

        if model not in ('open', 'presence'):
            raise ValueError('Invalid access model')

        result = yield self.get_node_configuration(node)

        raise_if_error(result)

        try:
            access_model = result.form['pubsub#access_model'].value
        except Exception:
            yield task.set_error('warning',
                                 condition='access-model-not-supported')

        if access_model == model:
            jid = self._client.get_bound_jid().new_as_bare()
            yield CommonResult(jid=jid)

        result.form['pubsub#access_model'].value = model

        self._log.info('Set access model %s', model)

        result = yield self.set_node_configuration(node, result.form)

        yield finalize(task, result)

    @iq_request_task
    def retract(self, node, id_, jid=None, notify=True):
        _task = yield

        response = yield _make_retract_request(node, id_, jid, notify)
        yield process_response(response)

    @iq_request_task
    def delete(self, node, jid=None):
        _task = yield

        response = yield _make_delete_request(node, jid)
        yield process_response(response)

    @iq_request_task
    def reconfigure_node(self, node, options, jid=None):
        _task = yield

        result = yield self.get_node_configuration(node, jid)
        if is_error(result):
            raise result

        _apply_options(result.form, options)
        result = yield self.set_node_configuration(node, result.form, jid)
        yield result

    @iq_request_task
    def set_node_configuration(self, node, form, jid=None):
        _task = yield

        response = yield _make_node_configuration(node, form, jid)
        yield process_response(response)

    @iq_request_task
    def get_node_configuration(self, node, jid=None):
        _task = yield

        response = yield _make_node_configuration_request(node, jid)

        if response.isError():
            raise PubSubStanzaError(response)

        jid = response.getFrom()
        form = _get_configure_form(response, node)
        yield PubSubNodeConfigurationResult(jid=jid, node=node, form=form)


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


def _get_pubsub_items(response, node):
    pubsub_node = response.getTag('pubsub', namespace=Namespace.PUBSUB)
    if pubsub_node is None:
        raise MalformedStanzaError('pubsub node missing', response)

    items_node = pubsub_node.getTag('items')
    if items_node is None:
        raise MalformedStanzaError('items node missing', response)

    if items_node.getAttr('node') != node:
        raise MalformedStanzaError('invalid node attr', response)

    return items_node.getTags('item')


def _get_pubsub_item(response, node, id_):
    items = _get_pubsub_items(response, node)

    if len(items) > 1:
        raise MalformedStanzaError('multiple items found', response)

    if not items:
        return None

    item = items[0]
    if item.getAttr('id') != id_:
        raise MalformedStanzaError('invalid item id', response)

    return item


def _make_pubsub_request(node, id_=None, max_items=None, jid=None):
    query = Iq('get', to=jid)
    pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB)
    items = pubsub.addChild('items', {'node': node})
    if max_items is not None:
        items.setAttr('max_items', max_items)
    if id_ is not None:
        items.addChild('item', {'id': id_})
    return query


def _get_configure_form(response, node):
    pubsub = response.getTag('pubsub', namespace=Namespace.PUBSUB_OWNER)
    if pubsub is None:
        raise MalformedStanzaError('pubsub node missing', response)

    configure = pubsub.getTag('configure')
    if configure is None:
        raise MalformedStanzaError('configure node missing', response)

    if node != configure.getAttr('node'):
        raise MalformedStanzaError('invalid node attribute', response)

    forms = configure.getTags('x', namespace=Namespace.DATA)
    for form in forms:
        dataform = extend_form(node=form)
        form_type = dataform.vars.get('FORM_TYPE')
        if form_type is None or form_type.value != Namespace.PUBSUB_CONFIG:
            continue

        return dataform

    raise MalformedStanzaError('no valid form type found', response)


def _get_published_item_id(response, node, id_):
    pubsub = response.getTag('pubsub', namespace=Namespace.PUBSUB)
    if pubsub is None:
        # https://xmpp.org/extensions/xep-0060.html#publisher-publish-success
        # If the publish request did not include an ItemID,
        # the IQ-result SHOULD include an empty <item/> element
        # that specifies the ItemID of the published item.
        #
        # If the server did not add a payload we assume the item was
        # published with the id we requested
        return id_

    publish = pubsub.getTag('publish')
    if publish is None:
        raise MalformedStanzaError('publish node missing', response)

    if node != publish.getAttr('node'):
        raise MalformedStanzaError('invalid node attribute', response)

    item = publish.getTag('item')
    if item is None:
        raise MalformedStanzaError('item node missing', response)

    item_id = item.getAttr('id')
    if id_ is not None and item_id != id_:
        raise MalformedStanzaError('invalid item id', response)

    return item_id


def _make_publish_request(node, item, id_, options, jid):
    query = Iq('set', to=jid)
    pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB)
    publish = pubsub.addChild('publish', {'node': node})
    attrs = {}
    if id_ is not None:
        attrs = {'id': id_}
    publish.addChild('item', attrs, [item])
    if options:
        publish = pubsub.addChild('publish-options')
        publish.addChild(node=_make_publish_options(options))
    return query


def _make_publish_options(options):
    data = Node(Namespace.DATA + ' x', attrs={'type': 'submit'})
    field = data.addChild('field', attrs={'var': 'FORM_TYPE', 'type': 'hidden'})
    field.setTagData('value', Namespace.PUBSUB_PUBLISH_OPTIONS)

    for var, value in options.items():
        field = data.addChild('field', attrs={'var': var})
        field.setTagData('value', value)
    return data


def _make_retract_request(node, id_, jid, notify):
    query = Iq('set', to=jid)
    pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB)
    attrs = {'node': node}
    if notify:
        attrs['notify'] = 'true'
    retract = pubsub.addChild('retract', attrs=attrs)
    retract.addChild('item', {'id': id_})
    return query


def _make_delete_request(node, jid):
    query = Iq('set', to=jid)
    pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB_OWNER)

    pubsub.addChild('delete', attrs={'node': node})
    return query


def _make_node_configuration(node, form, jid):
    query = Iq('set', to=jid)
    pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB_OWNER)
    configure = pubsub.addChild('configure', {'node': node})
    form.setAttr('type', 'submit')
    configure.addChild(node=form)
    return query


def _make_node_configuration_request(node, jid):
    query = Iq('get', to=jid)
    pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB_OWNER)
    pubsub.addChild('configure', {'node': node})
    return query


def _apply_options(form, options):
    for var, value in options.items():
        try:
            field = form[var]
        except KeyError:
            pass
        else:
            field.value = value


PubSubNodeConfigurationResult = namedtuple('PubSubConfigResult',
                                           'jid node form')

PubSubConfigResult = namedtuple('PubSubConfigResult',
                                'jid node form')

PubSubPublishResult = namedtuple('PubSubPublishResult',
                                 'jid node id')
