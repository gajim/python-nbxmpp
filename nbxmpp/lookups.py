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

from collections import defaultdict

from typing import Any
from typing import Optional

from lxml import etree

from nbxmpp.elements import Base

class ClassAtrributeLookup(etree.PythonElementClassLookup):

    _class_lookups: dict(str, dict(str, dict(str, Any))) = defaultdict(lambda: defaultdict(dict))

    @classmethod
    def register(cls, tag: str, attr: str, value: Optonal[str], element_class: Any):
        cls._class_lookups[tag][attr][value] = element_class

    def lookup(self, _document: Any, element: etree._Element) -> Optional[Any]:
        attribute_lookups = self._class_lookups.get(element.tag)
        if attribute_lookups is None:
            return None

        for attr, value_class_dict in attribute_lookups.items():
            value = element.get(attr)
            class_ = value_class_dict.get(value)
            if class_ is None:
                continue
            return class_

        return None


class SubElementLookup(etree.PythonElementClassLookup):

    _class_lookups: dict(str, dict(str, Any)) = defaultdict(dict)

    @classmethod
    def register(cls, tag: str, sub_tag: str, element_class: Any):
        cls._class_lookups[tag][sub_tag] = element_class

    def lookup(self, _document: Any, element: etree._Element) -> Optional[Any]:
        sub_lookups = self._class_lookups.get(element.tag)
        if sub_lookups is None:
            return None

        for child in list(element):
            element_class = sub_lookups.get(child.tag)
            if element_class is not None:
                return element_class

        return None


def register_attribute_lookup(tag: str,
                              attr: str,
                              value: Optional[str],
                              element_class: Any):
    ClassAtrributeLookup.register(tag, attr, value, element_class)


def register_sub_element_lookup(tag: str,
                                sub_tag: str,
                                element_class: Any):
    SubElementLookup.register(tag, sub_tag, element_class)


def register_class_lookup(tag: str,
                          namespace: str,
                          element_class: Any):
    
    _NamespaceLookup.get_namespace(namespace)[tag] = element_class


# Fallback order is important
_BaseLookup = etree.ElementDefaultClassLookup(element=Base)
_NamespaceLookup = etree.ElementNamespaceClassLookup(fallback=_BaseLookup)
_SubElementLookup = SubElementLookup(fallback=_NamespaceLookup)
_ClassAtrributeLookup = ClassAtrributeLookup(fallback=_SubElementLookup)

ElementLookup = _ClassAtrributeLookup
