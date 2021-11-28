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
from typing import Iterator
from typing import Optional
from typing import Union
from typing import Iterable

import copy

from nbxmpp.elements import Base
from nbxmpp.lookups import register_attribute_lookup
from nbxmpp.lookups import register_class_lookup
from nbxmpp.namespaces import Namespace
from nbxmpp.exceptions import WrongFieldValue
from nbxmpp.jid import JID


FIELD_TAG = '{%s}field' % Namespace.DATA


class DataField(Base):

    @property
    def is_multi_value_field(self):
        return False

    @property
    def type(self) -> str:
        return self.get('type', 'text-single')

    def set_type(self, value: str):
        self.set('type', value)

    @property
    def var(self) -> Optional[str]:
        return self.get('var')

    def set_var(self, value: str):
        self.set('var', value)

    def remove_var(self):
        self.attrib.pop('var', '')

    @property
    def label(self) -> Optional[str]:
        return self.get('label', self.var or None)

    def set_label(self, value: str):
        self.set('label', value)

    def remove_label(self):
        self.attrib.pop('label', '')

    @property
    def description(self) -> Optional[str]:
        return self.find_tag_text('desc') or None

    def set_description(self, value: str):
        self.add_tag_text('desc', value)

    def remove_description(self):
        self.remove_tag('desc')

    @property
    def required(self) -> bool:
        return bool(self.find_tag('required'))

    def set_required(self, value: bool):
        required = self.find_tag('required')
        exists = required is not None
        if not exists and value:
            self.add_tag('required')

        elif exists and not value:
            self.remove(required)

    @property
    def media(self) -> Optional[Base]:
        return self.find_tag('media', namespace=Namespace.DATA_MEDIA)

    def add_media(self) -> Base:
        media = self.media
        if media is None:
            return self.add_tag('media',namespace=Namespace.DATA_MEDIA)
        return media

    def remove_media(self):
        media = self.media
        if media is not None:
            self.remove(media)

    def is_valid(self) -> tuple[bool, str]:
        return True, ''


class Uri(Base):
    TAG = 'uri'
    NAMESPACE = Namespace.DATA_MEDIA

    @property
    def type(self) -> Optional[str]:
        return self.get('type')

    def set_type(self, value: str):
        self.set('type', value)


class Media(Base):
    TAG = 'media'
    NAMESPACE = Namespace.DATA_MEDIA

    @property
    def uris(self) -> list[Base]:
        return self.find_tags('uri')

    def set_uris(self, uris: list[str]):
        for uri in uris:
            self.add_tag_text('uri', uri)

    def remove_uris(self):
        for uri in self.find_tags('uri'):
            self.remove(uri)


class BooleanField(DataField):

    @property
    def value(self) -> bool:
        value = self.find_tag_text('value')
        if value in ('0', 'false'):
            return False
        if value in ('1', 'true'):
            return True
        return False

    def set_value(self, value: Union[str, bool, int]):
        if value in ['0', 'false', 0, False]:
            value = 'false'
        elif value in ['1', 'true', 1, True]:
            value = 'true'
        else:
            raise ValueError('Invalid value for boolean field: %s' % value)
        self.add_tag_text('value', value)


class StringField(DataField):

    @property
    def value(self) -> Optional[str]:
        return self.find_tag_text('value')

    def set_value(self, value: Any):
        if value is None:
            value = ''
        self.add_tag_text('value', str(value))

    def is_valid(self) -> tuple[bool, str]:
        if not self.required:
            return True, ''
        if not self.value:
            return False, ''
        return True, ''


class ListField(DataField):

    @property
    def options(self) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        for element in self.find_tags('option'):
            value = element.find_tag_text('value')
            if value is None:
                raise WrongFieldValue
            label = element.get('label')
            if not label:
                label = value
            options.append((label, value))
        return options

    def add_option(self, value: str, label: Optional[str]):
        element = self.add_tag('option')
        if label is not None:
            element.set('label', label)
        element.add_tag_text('value', value)

    def set_options(self, values: list[tuple[str, str]]):
        for value in values:
            self.add_option(*value)

    def remove_options(self):
        for element in self.find_tags('option'):
            self.remove(element)

    def iter_options(self):
        for element in self.find_tags('option'):
            value = element.find_tag_text('value')
            if value is None:
                raise WrongFieldValue
            label = element.get('label')
            if not label:
                label = value
            yield (value, label)


class ListSingleField(ListField, StringField):
    pass


class JidSingleField(StringField):

    def is_valid(self) -> tuple[bool, str]:
        if self.value:
            try:
                JID.from_string(self.value)
                return True, ''
            except Exception as error:
                return False, str(error)

        if self.required:
            return False, ''
        return True, ''


class ListMultiField(ListField):

    @property
    def is_multi_value_field(self):
        return True

    @property
    def values(self) -> list[str]:
        values: list[str] = []
        for element in self.find_tags('value'):
            if not element.text:
                raise WrongFieldValue
            values.append(element.text)
        return values

    def add_value(self, value: str):
        self.add_tag_text('value', value)

    def set_values(self, values: list[str]):
        for value in values:
            self.add_value(value)

    def remove_values(self):
        for element in self.find_tags('value'):
            self.remove(element)

    def iter_values(self) -> Iterable[str]:
        for element in self.find_tags('value'):
            if not element.text:
                raise WrongFieldValue
            yield element.text

    def is_valid(self) -> tuple[bool, str]:
        if not self.required:
            return True, ''
        if not self.values:
            return False, ''
        return True, ''


class JidMultiField(ListMultiField):

    def is_valid(self) -> tuple[bool, str]:
        if self.values:
            for value in self.values:
                try:
                    JID.from_string(value)
                except Exception as error:
                    return False, str(error)
            return True, ''
        if self.required:
            return False, ''
        return True, ''


class TextMultiField(DataField):

    @property
    def value(self):
        elements = [element.text or '' for
                    element in self.find_tags('value')]
        return '\n'.join(elements)

    def set_value(self, value: Optional[str]):
        self.remove_value()
        if not value:
            return

        for line in value.split('\n'):
            self.add_tag_text('value', line)

    def remove_value(self):
        value_tag = self.find_tag('value')
        if value_tag is not None:
            self.remove(value_tag)

    def is_valid(self) -> tuple[bool, str]:
        if not self.required:
            return True, ''
        if not self.value:
            return False, ''
        return True, ''


class DataRecord(Base):

    @property
    def fields(self) -> list[DataField]:
        return self.find_tags('field')

    def has_fields(self) -> bool:
        return bool(self.find_tags('fields'))

    def get_field(self, var: str) -> Optional[DataField]:
        for field in self.iter_fields():
            if field.var == var:
                return field

    def add_field(self,
                  type_: str,
                  var: Optional[str] = None,
                  label: Optional[str] = None,
                  description: Optional[str] = None,
                  required: bool = False) -> DataField:

        field: DataField = self.add_tag('field', type=type_)
        if var is not None:
            field.set_var(var)
        if label is not None:
            field.set_label(label)
        if description is not None:
            field.set_description(description)
        field.set_required(required)
        return field

    def set_form_type(self, namespace: str):
        field = self.add_field('hidden', var='FORM_TYPE')
        field.set_value(namespace)

    def get_form_type(self) -> Optional[str]:
        field = self.get_field('FORM_TYPE')
        if field is None:
            return None
        return field.value

    def type_is(self, namespace: str) -> bool:
        return namespace == self.get_form_type()

    def remove_fields(self):
        self.remove_tags('field')

    def remove_field(self, field: Base):
        self.remove(field)

    def iter_fields(self) -> Iterator[DataField]:
        for field in self.find_tags('field'):
            yield field

    def is_valid(self) -> bool:
        for field in self.iter_fields():
            if not field.is_valid()[0]:
                return False
        return True

    def is_fake_form(self) -> bool:
        return self.get_field('fakeform') is not None


class Item(DataRecord):
    pass


class DataFormBase(Base):

    @property
    def type(self) -> Optional[str]:
        return self.get('type')

    def set_type(self, type_: str):
        if type_ not in ('form', 'submit', 'cancel', 'result'):
            raise WrongFieldValue
        self.set('type', type_)

    @property
    def title(self) -> Optional[str]:
        return self.find_tag_text('title')

    def set_title(self, title: str):
        self.add_tag_text('title', title)

    def remove_title(self):
        self.remove_tag('title')

    @property
    def instructions(self):
        elements = [element.text or '' for
                    element in self.find_tags('instructions')]
        return '\n'.join(elements)

    def set_instructions(self, instructions: str):
        self.remove_instructions()
        for line in instructions.split('\n'):
            self.add_tag_text('instruction', line)

    def remove_instructions(self):
        for instruction in self.find_tags('instructions'):
            self.remove(instruction)

    @property
    def is_reported(self):
        return self.has_tag('reported')

    @property
    def records(self) -> list[Item]:
        return list(self.iter_records())

    def add_record(self) -> Item:
        return self.add_tag('item')

    def remove_record(self, record: Item):
        self.remove(record)

    def remove_records(self):
        self.remove_tags('item')

    def iter_records(self) -> Item:
        for record in self.find_tags('item'):
            yield record


class DataForm(DataFormBase, DataRecord):

    def cleanup(self) -> DataForm:
        dataform = copy.deepcopy(self)

        dataform.remove_title()
        dataform.remove_instructions()

        for field in dataform.fields:
            cleanup_field(field)

            if field.required:
                # Keep all required fields
                continue

            if isinstance(field, ListMultiField):
                if not field.values:
                    dataform.remove_field(field)
                continue

            if not field.value:
                dataform.remove_field(field)

        return dataform


def cleanup_field(field: DataField):
    field.remove_label()
    field.remove_description()
    field.remove_media()


register_attribute_lookup(FIELD_TAG, 'type', 'boolean', BooleanField)
register_attribute_lookup(FIELD_TAG, 'type', 'fixed', StringField)
register_attribute_lookup(FIELD_TAG, 'type', 'hidden', StringField)
register_attribute_lookup(FIELD_TAG, 'type', 'text-private', StringField)
register_attribute_lookup(FIELD_TAG, 'type', None, StringField)
register_attribute_lookup(FIELD_TAG, 'type', 'text-single', StringField)
register_attribute_lookup(FIELD_TAG, 'type', 'jid-single', JidSingleField)
register_attribute_lookup(FIELD_TAG, 'type', 'jid-multi', JidMultiField)
register_attribute_lookup(FIELD_TAG, 'type', 'list-single', ListSingleField)
register_attribute_lookup(FIELD_TAG, 'type', 'list-multi', ListMultiField)
register_attribute_lookup(FIELD_TAG, 'type', 'text-multi', TextMultiField)

register_class_lookup('x', Namespace.DATA, DataForm)
register_class_lookup('item', Namespace.DATA, Item)
