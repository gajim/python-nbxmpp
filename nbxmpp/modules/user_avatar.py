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

from typing import List
from typing import Optional
from typing import Dict

import hashlib
from dataclasses import dataclass
from dataclasses import asdict
from dataclasses import field

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import Node
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import b64encode
from nbxmpp.util import b64decode
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import raise_if_error
from nbxmpp.modules.util import finalize


class UserAvatar(BaseModule):

    _depends = {
        'publish': 'PubSub',
        'request_item': 'PubSub',
        'request_items': 'PubSub',
        'purge': 'PubSub',
    }

    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_avatar,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16),
        ]

    def _process_pubsub_avatar(self, _client, stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.AVATAR_METADATA:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        metadata = item.getTag('metadata', namespace=Namespace.AVATAR_METADATA)
        if metadata is None:
            self._log.warning('No metadata node found')
            self._log.warning(stanza)
            raise NodeProcessed

        if not metadata.getChildren():
            self._log.info('Received avatar metadata: %s - no avatar set',
                           properties.jid)
            return

        try:
            data = AvatarMetaData.from_node(metadata, item.getAttr('id'))
        except Exception as error:
            self._log.warning('Malformed user avatar data: %s', error)
            self._log.warning(stanza)
            raise NodeProcessed

        pubsub_event = properties.pubsub_event._replace(data=data)
        self._log.info('Received avatar metadata: %s - %s',
                       properties.jid, data)

        properties.pubsub_event = pubsub_event

    @iq_request_task
    def request_avatar_data(self, id_, jid=None):
        task = yield

        item = yield self.request_item(Namespace.AVATAR_DATA,
                                       id_=id_,
                                       jid=jid)

        raise_if_error(item)

        if item is None:
            yield task.set_result(None)

        yield _get_avatar_data(item, id_)

    @iq_request_task
    def request_avatar_metadata(self, jid=None):
        task = yield

        items = yield self.request_items(Namespace.AVATAR_METADATA,
                                         max_items=1,
                                         jid=jid)

        raise_if_error(items)

        if not items:
            yield task.set_result(None)

        item = items[0]
        metadata = item.getTag('metadata', namespace=Namespace.AVATAR_METADATA)
        if metadata is None:
            raise MalformedStanzaError('metadata node missing', item)

        if not metadata.getChildren():
            yield task.set_result(None)

        yield AvatarMetaData.from_node(metadata, item.getAttr('id'))

    @iq_request_task
    def set_avatar(self, avatar, public=False):

        task = yield

        access_model = 'open' if public else 'presence'

        if avatar is None:
            result = yield self._publish_avatar_metadata(None, access_model)
            raise_if_error(result)

            result = yield self.purge(Namespace.AVATAR_DATA)
            yield finalize(task, result)

        result = yield self._publish_avatar(avatar, access_model)

        yield finalize(task, result)

    @iq_request_task
    def _publish_avatar(self, avatar, access_model):
        task = yield

        options = {
            'pubsub#persist_items': 'true',
            'pubsub#access_model': access_model,
        }

        for info, data in avatar.pubsub_avatar_info():
            item = _make_avatar_data_node(data)

            result = yield self.publish(Namespace.AVATAR_DATA,
                                        item,
                                        id_=info.id,
                                        options=options,
                                        force_node_options=True)

            raise_if_error(result)

        result = yield self._publish_avatar_metadata(avatar.metadata,
                                                     access_model)

        yield finalize(task, result)

    @iq_request_task
    def _publish_avatar_metadata(self, metadata, access_model):
        task = yield

        options = {
            'pubsub#persist_items': 'true',
            'pubsub#access_model': access_model,
        }

        if metadata is None:
            metadata = AvatarMetaData()

        result = yield self.publish(Namespace.AVATAR_METADATA,
                                    metadata.to_node(),
                                    id_=metadata.default,
                                    options=options,
                                    force_node_options=True)

        yield finalize(task, result)

    @iq_request_task
    def set_access_model(self, public):
        task = yield

        access_model = 'open' if public else 'presence'

        result = yield self._client.get_module('PubSub').set_access_model(
            Namespace.AVATAR_DATA, access_model)

        raise_if_error(result)

        result = yield self._client.get_module('PubSub').set_access_model(
            Namespace.AVATAR_METADATA, access_model)

        yield finalize(task, result)


def _get_avatar_data(item, id_):
    data_node = item.getTag('data', namespace=Namespace.AVATAR_DATA)
    if data_node is None:
        raise MalformedStanzaError('data node missing', item)

    data = data_node.getData()
    if not data:
        raise MalformedStanzaError('data node empty', item)

    try:
        avatar = b64decode(data)
    except Exception as error:
        raise MalformedStanzaError(f'decoding error: {error}', item)

    avatar_sha = hashlib.sha1(avatar).hexdigest()
    if avatar_sha != id_:
        raise MalformedStanzaError('avatar does not match sha', item)

    return AvatarData(data=avatar, sha=avatar_sha)


def _make_metadata_node(infos):
    item = Node('metadata', attrs={'xmlns': Namespace.AVATAR_METADATA})
    for info in infos:
        item.addChild('info', attrs=info.to_dict())
    return item


def _make_avatar_data_node(avatar):
    item = Node('data', attrs={'xmlns': Namespace.AVATAR_DATA})
    item.setData(b64encode(avatar.data))
    return item


def _get_info_attrs(avatar, avatar_sha, height, width):
    info_attrs = {
        'id': avatar_sha,
        'bytes': len(avatar),
        'type': 'image/png',
    }

    if height is not None:
        info_attrs['height'] = height

    if width is not None:
        info_attrs['width'] = width

    return info_attrs


@dataclass
class AvatarInfo:
    bytes: int
    id: str
    type: str
    url: str = None
    height: int = None
    width: int = None

    def __post_init__(self):
        if self.bytes is None:
            raise ValueError
        if self.id is None:
            raise ValueError
        if self.type is None:
            raise ValueError

        self.bytes = int(self.bytes)

        if self.height is not None:
            self.height = int(self.height)
        if self.width is not None:
            self.width = int(self.width)

    def to_dict(self):
        info_dict = asdict(self)
        if self.height is None:
            info_dict.pop('height')
        if self.width is None:
            info_dict.pop('width')
        if self.url is None:
            info_dict.pop('url')
        return info_dict

    def __hash__(self):
        return hash(self.id)


@dataclass
class AvatarData:
    data: bytes
    sha: str


@dataclass
class AvatarMetaData:
    infos: List[AvatarInfo] = field(default_factory=list)
    default: Optional[str] = None

    @classmethod
    def from_node(cls, node, default=None):
        infos = []
        info_nodes = node.getTags('info')
        for info in info_nodes:
            infos.append(AvatarInfo(
                bytes=info.getAttr('bytes'),
                id=info.getAttr('id'),
                type=info.getAttr('type'),
                url=info.getAttr('url'),
                height=info.getAttr('height'),
                width=info.getAttr('width')
            ))
        return cls(infos=infos, default=default)

    def add_avatar_info(self, avatar_info, make_default=False):
        self.infos.append(avatar_info)
        if make_default:
            self.default = avatar_info.id

    def to_node(self):
        return _make_metadata_node(self.infos)

    @property
    def avatar_shas(self):
        return [info.id for info in self.infos]


@dataclass
class Avatar:
    metadata: AvatarMetaData = field(default_factory=AvatarMetaData)
    data: Dict[AvatarInfo, bytes] = field(init=False, default_factory=dict)

    def add_image_source(self,
                         data,
                         type_,
                         height,
                         width,
                         url=None,
                         make_default=True):

        sha = hashlib.sha1(data).hexdigest()
        info = AvatarInfo(bytes=len(data),
                          id=sha,
                          type=type_,
                          height=height,
                          width=width,
                          url=url)
        self.metadata.add_avatar_info(info, make_default=make_default)
        self.data[info] = AvatarData(data=data, sha=sha)

    def pubsub_avatar_info(self):
        for info, data in self.data.items():
            if info.url is not None:
                continue
            yield info, data
