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

from typing import Iterable
from typing import Optional

import logging

from nbxmpp import types
from nbxmpp.client import Client
from nbxmpp.elements import Base
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.jid import JID
from nbxmpp.lookups import register_class_lookup
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize
from nbxmpp.modules.util import raise_if_error
from nbxmpp.namespaces import Namespace
from nbxmpp.task import iq_request_task


log = logging.getLogger('nbxmpp.m.vcard4')


ALLOWED_SEX_VALUES = ['M', 'F', 'O', 'N', 'U']
ALLOWED_KIND_VALUES = ['individual', 'group', 'org', 'location']

# Cardinality
# 1     Exactly one instance per vCard MUST be present.
# *1    Exactly one instance per vCard MAY be present.
# 1*    One or more instances per vCard MUST be present.
# *     One or more instances per vCard MAY be present.

PROPERTY_DEFINITION: dict[str, tuple[list[str], str]] = {
    'source': (['altid', 'pid', 'pref', 'mediatype'], '*'),
    'kind': ([], '*1'),
    'fn': (['language', 'altid', 'pid', 'pref', 'type'], '1*'),
    'n': (['language', 'altid', 'sort-as'], '*1'),
    'nickname': (['language', 'altid', 'pid', 'pref', 'type'], '*'),
    'photo': (['altid', 'pid', 'pref', 'type', 'mediatype'], '*'),
    'bday': (['altid', 'calscale'], '*1'),
    'anniversary': (['altid', 'calscale'], '*1'),
    'gender': ([], '*1'),
    'adr': (['language', 'altid', 'pid', 'pref', 'type', 'geo', 'tz', 'label'], '*'),
    'tel': (['altid', 'pid', 'pref', 'type', 'mediatype'], '*'),
    'email': (['altid', 'pid', 'pref', 'type'], '*'),
    'impp': (['altid', 'pid', 'pref', 'type', 'mediatype'], '*'),
    'lang': (['altid', 'pid', 'pref', 'type'], '*'),
    'tz': (['altid', 'pid', 'pref', 'type', 'mediatype'], '*'),
    'geo': (['altid', 'pid', 'pref', 'type', 'mediatype'], '*'),
    'title': (['language', 'altid', 'pid', 'pref', 'type'], '*'),
    'role': (['language', 'altid', 'pid', 'pref', 'type'], '*'),
    'logo': (['language', 'altid', 'pid', 'pref', 'type', 'mediatype'], '*'),
    'org': (['language', 'altid', 'pid', 'pref', 'type', 'sort-as'], '*'),
    'member': (['altid', 'pid', 'pref', 'mediatype'], '*'),
    'related': (['altid', 'pid', 'pref', 'type', 'mediatype'], '*'),
    'categories': (['altid', 'pid', 'pref', 'type'], '*'),
    'note': (['language', 'altid', 'pid', 'pref', 'type'], '*'),
    'prodid': ([], '*1'),
    'rev': ([], '*1'),
    'sound': (['language', 'altid', 'pid', 'pref', 'type', 'mediatype'], '*'),
    'uid': ([], '*1'),
    'clientpidmap': ([], '*'),
    'url': (['altid', 'pid', 'pref', 'type', 'mediatype'], '*'),
    'key': (['altid', 'pid', 'pref', 'type', 'mediatype'], '*'),
    'fburl': (['altid', 'pid', 'pref', 'type', 'mediatype'], '*'),
    'caladruri': (['altid', 'pid', 'pref', 'type', 'mediatype'], '*'),
    'caluri': (['altid', 'pid', 'pref', 'type', 'mediatype'], '*'),
}


PROPERTY_VALUE_TYPES = {
    'bday': ['date', 'time', 'date-time', 'text'],
    'anniversary': ['date', 'time', 'date-time', 'text'],
    'key': ['text', 'uri'],
    'tel': ['text', 'uri'],
    'tz': ['text', 'uri', 'utc-offset'],
    'related': ['text', 'uri'],
}


def get_data_from_children(element: types.Base, child_name: str) -> list[str]:
    values: list[str] = []
    child_nodes = element.find_tags(child_name)
    for child_node in child_nodes:
        child_value = child_node.text or ''
        if child_value:
            values.append(child_value)
    return values


def get_multiple_type_value(element: types.Base,
                            types: list[str]) -> tuple[str, str]:
    for type_ in types:
        value = element.find_tag_text(type_)
        if value:
            return type_, value

    raise ValueError('no value found')


class BaseParameter(Base):

    @property
    def name(self) -> str:
        return self.localname


class SingleParameter(BaseParameter):
    _type: str = ''

    @property
    def value(self):
        return self.find_tag_text(self._type)

    def set_value(self, value: str):
        self.add_tag_text(self._type, value)


class MultiParameter(BaseParameter):
    _type: str = 'text'

    @property
    def values(self) -> set[str]:
        tags = self.find_tags(self._type)
        if not tags:
            raise ValueError('no parameter value found')

        values = {tag.text for tag in tags if tag.text}
        return values

    def set_values(self, values: Iterable[str]):
        self.remove_tags(self._type)
        for value in values:
            tag = self.add_tag(self._type)
            tag.text = value


class TextParameter(SingleParameter):
    _type = 'text'


class LanguageParameter(SingleParameter):
    _type = 'language-tag'


class PrefParameter(SingleParameter):
    _type = 'integer'


class GeoParameter(SingleParameter):
    _type = 'uri'


class TzParameter(BaseParameter):

    @property
    def type(self) -> str:
        value_type, _ = get_multiple_type_value(self, ['text', 'uri'])
        return value_type

    @property
    def value(self) -> str:
        _, value = get_multiple_type_value(self, ['text', 'uri'])
        return value

    def set_value(self, type: str, value: str):
        self.add_tag_text(self.type, value)


class BaseProperty(Base):

    @property
    def name(self) -> str:
        return self.localname

    def get_parameter(self, name: str):
        return self.find_tag(name)

    def remove_parameter(self, name: str):
        self.remove_tag(name)

    def add_parameter(self, name: str) -> BaseParameter:
        return self.add_tag(name)

    @property
    def parameters(self) -> list[BaseParameter]:
        return list(self.find_tag('parameters'))


class SingleProperty(BaseProperty):
    _type: str = ''

    @property
    def value(self) -> Optional[str]:
        return self.find_tag_text(self._type)

    def set_value(self, value: str):
        self.add_tag_text(self._type, value)


class UriProperty(SingleProperty):
    _type: str = 'uri'


class TextProperty(SingleProperty):
    _type: str = 'text'


class RevProperty(SingleProperty):
    _type: str = 'timestamp'


class LangProperty(Base):
    _type: str = 'language-tag'


class TextListProperty(BaseProperty):

    @property
    def values(self):
        return get_data_from_children(self, 'text')

    def set_values(self, values: Iterable[str]):
        for value in values:
            tag = self.add_tag('text')
            tag.text = value


class MultiProperty(BaseProperty):

    @property
    def type(self) -> str:
        types = PROPERTY_VALUE_TYPES[self.name]
        value_type, _ = get_multiple_type_value(self, types)
        return value_type

    @property
    def value(self) -> str:
        types = PROPERTY_VALUE_TYPES[self.name]
        _, value = get_multiple_type_value(self, types)
        return value

    def set_value(self, type: str, value: str):
        self.add_tag_text(type, value)


class NProperty(BaseProperty):

    @property
    def surname(self) -> list[str]:
        return get_data_from_children(self, 'surname')

    @property
    def given(self) -> list[str]:
        return get_data_from_children(self, 'given')

    @property
    def additional(self) -> list[str]:
        return get_data_from_children(self, 'additional')

    @property
    def prefix(self) -> list[str]:
        return get_data_from_children(self, 'prefix')

    @property
    def suffix(self) -> list[str]:
        return get_data_from_children(self, 'suffix')

    def set_attribute(self, name: str, values: Iterable[str]):
        if name not in ['surname', 'given', 'additional', 'prefix', 'suffix']:
            raise ValueError('unknown name: %s' % name)

        self.remove_tags(name)
        for value in values:
            tag = self.add_tag(name)
            tag.text = value

    @property
    def is_empty(self):
        if (self.surname or
                self.given or
                self.additional or
                self.suffix or
                self.prefix):
            return False
        return True


class GenderProperty(BaseProperty):

    @property
    def sex(self) -> Optional[str]:
        sex = self.find_tag_text('sex')
        if sex not in ALLOWED_SEX_VALUES:
            sex = None
        return sex

    @property
    def identity(self) -> Optional[str]:
        return self.find_tag_text('identity')

    def set_attribute(self, name: str, value: str):
        self.remove_tags(name)
        tag = self.add_tag(name)
        tag.text = value

    @property
    def is_empty(self):
        if self.sex or self.identity:
            return False
        return True


class AdrProperty(Base):

    @property
    def pobox(self) -> list[str]:
        return get_data_from_children(self, 'pobox')

    @property
    def ext(self) -> list[str]:
        return get_data_from_children(self, 'ext')

    @property
    def street(self) -> list[str]:
        return get_data_from_children(self, 'street')

    @property
    def locality(self) -> list[str]:
        return get_data_from_children(self, 'locality')

    @property
    def region(self) -> list[str]:
        return get_data_from_children(self, 'region')

    @property
    def code(self) -> list[str]:
        return get_data_from_children(self, 'code')

    @property
    def country(self) -> list[str]:
        return get_data_from_children(self, 'country')

    def set_attribute(self, name: str, value: str):
        self.remove_tags(name)
        tag = self.add_tag(name)
        tag.text = value

    @property
    def is_empty(self):
        # pylint: disable=too-many-boolean-expressions
        if (self.pobox or
                self.ext or
                self.street or
                self.locality or
                self.region or
                self.code or
                self.country):
            return False
        return True


class ClientpidmapProperty(BaseProperty):

    @property
    def sourceid(self) -> Optional[str]:
        return self.find_tag_text('sourceid')

    @property
    def uri(self) -> Optional[str]:
        return self.find_tag_text('uri')

    def set_attribute(self, name: str, value: str):
        self.remove_tags(name)
        tag = self.add_tag(name)
        tag.text = value

    @property
    def is_empty(self):
        return not self.uri


class VCard(Base):

    def get_properties(self) -> list[BaseProperty]:
        return list(self)

    def add_property(self, name: str) -> BaseProperty:
        return self.add_tag(name)

    def remove_property(self, name: str):
        self.remove_tags(name)



class VCard4(BaseModule):

    _depends = {
        'publish': 'PubSub',
        'request_items': 'PubSub',
    }

    def __init__(self, client: Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def request_vcard(self, jid: Optional[JID] = None):

        items = yield self.request_items(Namespace.VCARD4_PUBSUB,
                                         jid=jid,
                                         max_items=1)

        raise_if_error(items)

        if not items:
            yield None

        item = items[0]

        vcard = item.find_tag('vcard', namespace=Namespace.VCARD4)
        if vcard is None:
            raise MalformedStanzaError('vcard node missing', item)

        return vcard

    @iq_request_task
    def set_vcard(self, vcard: VCard, public: bool = False):

        access_model = 'open' if public else 'presence'

        options = {
            'pubsub#persist_items': 'true',
            'pubsub#access_model': access_model,
        }

        result = yield self.publish(Namespace.VCARD4_PUBSUB,
                                    vcard,
                                    id_='current',
                                    options=options,
                                    force_node_options=True)

        yield finalize(result)


register_class_lookup('vcard', Namespace.VCARD4, VCard)

register_class_lookup('fburl', Namespace.VCARD4, UriProperty)
register_class_lookup('caladruri', Namespace.VCARD4, UriProperty)
register_class_lookup('calurl', Namespace.VCARD4, UriProperty)
register_class_lookup('source', Namespace.VCARD4, UriProperty)
register_class_lookup('photo', Namespace.VCARD4, UriProperty)
register_class_lookup('impp', Namespace.VCARD4, UriProperty)
register_class_lookup('geo', Namespace.VCARD4, UriProperty)
register_class_lookup('logo', Namespace.VCARD4, UriProperty)
register_class_lookup('member', Namespace.VCARD4, UriProperty)
register_class_lookup('sound', Namespace.VCARD4, UriProperty)
register_class_lookup('uid', Namespace.VCARD4, UriProperty)

register_class_lookup('kind', Namespace.VCARD4, TextProperty)
register_class_lookup('fn', Namespace.VCARD4, TextProperty)
register_class_lookup('email', Namespace.VCARD4, TextProperty)
register_class_lookup('title', Namespace.VCARD4, TextProperty)
register_class_lookup('role', Namespace.VCARD4, TextProperty)
register_class_lookup('note', Namespace.VCARD4, TextProperty)
register_class_lookup('prodid', Namespace.VCARD4, TextProperty)

register_class_lookup('nickname', Namespace.VCARD4, TextListProperty)
register_class_lookup('org', Namespace.VCARD4, TextListProperty)
register_class_lookup('categories', Namespace.VCARD4, TextListProperty)

register_class_lookup('bday', Namespace.VCARD4, MultiProperty)
register_class_lookup('anniversary', Namespace.VCARD4, MultiProperty)
register_class_lookup('tz', Namespace.VCARD4, MultiProperty)
register_class_lookup('tel', Namespace.VCARD4, MultiProperty)
register_class_lookup('related', Namespace.VCARD4, MultiProperty)
register_class_lookup('key', Namespace.VCARD4, MultiProperty)

register_class_lookup('n', Namespace.VCARD4, NProperty)
register_class_lookup('gender', Namespace.VCARD4, GenderProperty)
register_class_lookup('adr', Namespace.VCARD4, AdrProperty)
register_class_lookup('lang', Namespace.VCARD4, LangProperty)
register_class_lookup('clientpidmap', Namespace.VCARD4, ClientpidmapProperty)

register_class_lookup('language', Namespace.VCARD4, LanguageParameter)
register_class_lookup('pref', Namespace.VCARD4, PrefParameter)
register_class_lookup('altid', Namespace.VCARD4, TextParameter)
register_class_lookup('mediatype', Namespace.VCARD4, TextParameter)
register_class_lookup('calscale', Namespace.VCARD4, TextParameter)
register_class_lookup('pid', Namespace.VCARD4, MultiParameter)
register_class_lookup('type', Namespace.VCARD4, MultiParameter)
register_class_lookup('sort-as', Namespace.VCARD4, MultiParameter)
register_class_lookup('tz', Namespace.VCARD4, TzParameter)

# TODO
# Needs special registration because there is already a geo property
# register_class_lookup('geo', Namespace.VCARD4, GeoParameter)
