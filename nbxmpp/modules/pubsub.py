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

from typing import Any, Generator
from typing import Literal
from typing import Optional
from typing import Union

from nbxmpp import types
from nbxmpp.task import iq_request_task
from nbxmpp.errors import is_error
from nbxmpp.errors import PubSubStanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import PubSubEventData
from nbxmpp.structs import CommonResult
from nbxmpp.structs import PubSubNodeConfigurationResult
from nbxmpp.structs import PubSubPublishResult
from nbxmpp.builder import Iq
from nbxmpp.jid import JID
from nbxmpp.builder import DataForm
from nbxmpp.namespaces import Namespace
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response
from nbxmpp.modules.util import raise_if_error
from nbxmpp.modules.util import finalize


RequestItemGenerator = Generator[Optional[Union[types.Iq, types.Base]], types.Iq, None]
RequestItemsGenerator = Generator[Union[types.Iq, list[types.Base]], types.Iq, None]


class PubSub(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_base,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=15),
        ]

    def _process_pubsub_base(self,
                             _client: types.Client,
                             stanza: types.Message,
                             properties: Any):

        event = stanza.find_tag('event', namespace=Namespace.PUBSUB_EVENT)
        if event is None:
            return

        properties.pubsub = True

        delete = event.find_tag('delete')
        if delete is not None:
            node = delete.get('node')
            properties.pubsub_event = PubSubEventData(node, deleted=True)
            return

        purge = event.find_tag('purge')
        if purge is not None:
            node = purge.get('node')
            properties.pubsub_event = PubSubEventData(node, purged=True)
            return

        items = event.find_tag('items')
        if items is not None:
            node = items.get('node')

            retract = items.find_tag('retract')
            if retract is not None:
                id_ = retract.get('id')
                properties.pubsub_event = PubSubEventData(
                    node, id_, retracted=True)
                return

            if len(items.get_children()) != 1:
                self._log.warning('PubSub event with != 1 item')
                self._log.warning(stanza)
                return

            item = items.find_tag('item')
            if item is None:
                self._log.warning('No item node found')
                self._log.warning(stanza)
                return
            id_ = item.get('id')
            properties.pubsub_event = PubSubEventData(node, id_, item)

    @iq_request_task
    def request_item(self,
                     node: str,
                     id_: str,
                     jid: Optional[JID] = None) -> RequestItemGenerator:

        response = yield _make_pubsub_request(node, id_=id_, jid=jid)

        if response.is_error():
            raise PubSubStanzaError(response)

        yield _get_pubsub_item(response, node, id_)

    @iq_request_task
    def request_items(self,
                      node: str,
                      max_items: Optional[str] = None,
                      jid: Optional[JID] = None) -> RequestItemsGenerator:

        response = yield _make_pubsub_request(node,
                                              max_items=max_items,
                                              jid=jid)

        if response.is_error():
            raise PubSubStanzaError(response)

        yield _get_pubsub_items(response, node)

    @iq_request_task
    def publish(self,
                node: str,
                item: types.Base,
                id_: Optional[str] = None,
                options: Optional[dict[str, str]] = None,
                jid: Optional[JID] = None,
                force_node_options: bool = False):

        request = _make_publish_request(node, item, id_, options, jid)
        response = yield request

        if response.is_error():
            error = PubSubStanzaError(response)
            if (not force_node_options or
                    error.app_condition != 'precondition-not-met'):
                raise error

            result = yield self.reconfigure_node(node, options, jid)
            if is_error(result):
                raise result

            response = yield request
            if response.is_error():
                raise PubSubStanzaError(response)

        jid = response.get_from()
        item_id = _get_published_item_id(response, node, id_)
        yield PubSubPublishResult(jid, node, item_id)

    @iq_request_task
    def get_access_model(self, node: str):

        result = yield self.get_node_configuration(node)

        raise_if_error(result)

        yield result.form['pubsub#access_model'].value

    @iq_request_task
    def set_access_model(self,
                         node: str,
                         model: Union[Literal['open'],
                                      Literal['presence']]):

        result = yield self.get_node_configuration(node)

        raise_if_error(result)

        field = result.form.get_field('pubsub#access_model')
        if field is None:
            yield MalformedStanzaError('pubsub#access_model feature not supported')

        if field.value == model:
            jid = self._client.get_bound_jid().new_as_bare()
            yield CommonResult(jid=jid)

        field.set_value(model)

        result = yield self.set_node_configuration(node, result.form)

        yield finalize(result)

    @iq_request_task
    def retract(self,
                node: str,
                id_: str,
                jid: Optional[JID] = None,
                notify: bool = True):


        response = yield _make_retract_request(node, id_, jid, notify)
        yield process_response(response)

    @iq_request_task
    def purge(self, node: str, jid: Optional[JID] = None):

        response = yield _make_purge_request(node, jid)
        yield process_response(response)

    @iq_request_task
    def delete(self, node: str, jid: Optional[JID] = None):

        response = yield _make_delete_request(node, jid)
        yield process_response(response)

    @iq_request_task
    def reconfigure_node(self,
                         node: str,
                         options: dict[str, str],
                         jid: Optional[JID] = None):

        result = yield self.get_node_configuration(node, jid)
        if is_error(result):
            raise result

        _apply_options(result.form, options)
        result = yield self.set_node_configuration(node, result.form, jid)
        yield result

    @iq_request_task
    def set_node_configuration(self,
                               node: str,
                               form: types.DataForm,
                               jid: Optional[JID] = None):

        response = yield _make_node_configuration(node, form, jid)
        yield process_response(response)

    @iq_request_task
    def get_node_configuration(self, node: str, jid: Optional[JID] = None):

        response = yield _make_node_configuration_request(node, jid)

        if response.is_error():
            raise PubSubStanzaError(response)

        jid = response.get_from()
        form = _get_configure_form(response, node)
        yield PubSubNodeConfigurationResult(jid=jid, node=node, form=form)


def get_pubsub_request(jid: JID,
                       node: str,
                       id_: Optional[str] = None,
                       max_items: Optional[str] = None) -> types.Iq:

    iq = Iq(to=jid)
    pubsub = iq.add_tag('pubsub', namespace=Namespace.PUBSUB)
    items = pubsub.add_tag('items', node=node)
    if max_items is not None:
        items.set('max_items', max_items)
    if id_ is not None:
        items.add_tag('item', id=id_)
    return iq


def get_pubsub_item(stanza: types.Iq) -> Optional[types.Base]:
    pubsub = stanza.find_tag('pubsub')
    if pubsub is None:
        return None

    items = pubsub.find_tag('items')
    if items is None:
        return None

    return items.find_tag('item')


def get_pubsub_items(stanza: types.Iq,
                     node: Optional[str] = None) -> Optional[list[types.Base]]:

    pubsub = stanza.find_tag('pubsub')
    if pubsub is None:
        return None

    items = pubsub.find_tag('items')
    if items is None:
        return None

    if node is not None and items.get('node') != node:
        return None
    return items.find_tags('item')


def get_publish_options(config: dict[str, str]) -> types.Base:
    options = DataForm(type='submit')
    options.set_form_type(Namespace.PUBSUB_PUBLISH_OPTIONS)

    for var, value in config.items():
        field = options.add_field('text-single', var=var)
        field.set_value(value)
    return options


def _get_pubsub_items(response: types.Iq, node: str) -> list[types.Base]:
    pubsub = response.find_tag('pubsub', namespace=Namespace.PUBSUB)
    if pubsub is None:
        raise MalformedStanzaError('pubsub node missing', response)

    items = pubsub.find_tag('items')
    if items is None:
        raise MalformedStanzaError('items node missing', response)

    if items.get('node') != node:
        raise MalformedStanzaError('invalid node attr', response)

    return items.find_tags('item')


def _get_pubsub_item(response: types.Iq,
                     node: str,
                     id_: str) -> Optional[types.Base]:

    items = _get_pubsub_items(response, node)

    if len(items) > 1:
        raise MalformedStanzaError('multiple items found', response)

    if not items:
        return None

    item = items[0]
    if item.get('id') != id_:
        raise MalformedStanzaError('invalid item id', response)

    return item


def _make_pubsub_request(node: str,
                         id_: Optional[str] = None,
                         max_items: Optional[str] = None,
                         jid: Optional[JID] = None):

    iq = Iq(to=jid)
    pubsub = iq.add_tag('pubsub', namespace=Namespace.PUBSUB)
    items = pubsub.add_tag('items', node=node)
    if max_items is not None:
        items.set('max_items', max_items)
    if id_ is not None:
        items.add_tag('item', id=id_)
    return iq


def _get_configure_form(response: types.Iq, node: str) -> types.DataForm:
    pubsub = response.find_tag('pubsub', namespace=Namespace.PUBSUB_OWNER)
    if pubsub is None:
        raise MalformedStanzaError('pubsub node missing', response)

    configure = pubsub.find_tag('configure')
    if configure is None:
        raise MalformedStanzaError('configure node missing', response)

    if node != configure.get('node'):
        raise MalformedStanzaError('invalid node attribute', response)

    forms = configure.find_tags('x', namespace=Namespace.DATA)
    for form in forms:
        if not form.type_is(Namespace.PUBSUB_CONFIG):
            continue

        return dataform

    raise MalformedStanzaError('no valid form type found', response)


def _get_published_item_id(response: types.Iq,
                           node: str,
                           id_: Optional[str]) -> Optional[str]:

    pubsub = response.find_tag('pubsub', namespace=Namespace.PUBSUB)
    if pubsub is None:
        # https://xmpp.org/extensions/xep-0060.html#publisher-publish-success
        # If the publish request did not include an ItemID,
        # the IQ-result SHOULD include an empty <item/> element
        # that specifies the ItemID of the published item.
        #
        # If the server did not add a payload we assume the item was
        # published with the id we requested
        return id_

    publish = pubsub.find_tag('publish')
    if publish is None:
        raise MalformedStanzaError('publish node missing', response)

    if node != publish.get('node'):
        raise MalformedStanzaError('invalid node attribute', response)

    item = publish.find_tag('item')
    if item is None:
        raise MalformedStanzaError('item node missing', response)

    item_id = item.get('id')
    if id_ is not None and item_id != id_:
        raise MalformedStanzaError('invalid item id', response)

    return item_id


def _make_publish_request(node: str,
                          item: types.Base,
                          id_: str,
                          options: dict[str, str],
                          jid: JID) -> types.Iq:

    iq = Iq(to=jid, type='set')
    pubsub = iq.add_tag('pubsub', namespace=Namespace.PUBSUB)
    publish = pubsub.add_tag('publish', node=node)
    attrs = {}
    if id_ is not None:
        attrs = {'id': id_}
    publish_item = publish.add_tag('item', **attrs)
    item.append(publish_item)
    if options:
        publish_options = pubsub.add_tag('publish-options')
        publish_options.append(get_publish_options(options))
    return iq


def _make_retract_request(node: str,
                          id_: str,
                          jid: JID,
                          notify: bool) -> types.Iq:

    iq = Iq(to=jid, type='set')
    pubsub = iq.add_tag('pubsub', namespace=Namespace.PUBSUB)
    attrs = {'node': node}
    if notify:
        attrs['notify'] = 'true'
    retract = pubsub.add_tag('retract', **attrs)
    retract.add_tag('item', id=id_)
    return iq


def _make_purge_request(node: str, jid: JID) -> types.Iq:
    iq = Iq(to=jid, type='set')
    pubsub = iq.add_tag('pubsub', namespace=Namespace.PUBSUB_OWNER)
    pubsub.add_tag('purge', node=node)
    return iq


def _make_delete_request(node: str, jid: JID) -> types.Iq:
    iq = Iq(to=jid, type='set')
    pubsub = iq.add_tag('pubsub', namespace=Namespace.PUBSUB_OWNER)
    pubsub.add_tag('delete', node=node)
    return iq


def _make_node_configuration(node: str,
                             form: types.DataForm,
                             jid: JID) -> types.Iq:

    iq = Iq(to=jid, type='set')
    pubsub = iq.add_tag('pubsub', namespace=Namespace.PUBSUB_OWNER)
    configure = pubsub.add_tag('configure', node=node)
    form.set_type('submit')
    configure.append(form)
    return iq


def _make_node_configuration_request(node: str, jid: JID) -> types.Iq:
    iq = Iq(to=jid)
    pubsub = iq.add_tag('pubsub', namespace=Namespace.PUBSUB_OWNER)
    pubsub.add_tag('configure', node=node)
    return iq


def _apply_options(form: types.DataForm, options: dict[str, str]):
    for var, value in options.items():
        field = form.get_field(var)
        if field is None:
            continue

        field.set_value(value)
