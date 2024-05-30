# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import TYPE_CHECKING

import logging
from collections.abc import ValuesView
from dataclasses import dataclass
from dataclasses import field

from nbxmpp.errors import MalformedStanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize
from nbxmpp.modules.util import raise_if_error
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.simplexml import Node
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client

log = logging.getLogger("nbxmpp.m.vcard4")


ALLOWED_SEX_VALUES = ["M", "F", "O", "N", "U"]
ALLOWED_KIND_VALUES = ["individual", "group", "org", "location"]

# Cardinality
# 1     Exactly one instance per vCard MUST be present.
# *1    Exactly one instance per vCard MAY be present.
# 1*    One or more instances per vCard MUST be present.
# *     One or more instances per vCard MAY be present.

PROPERTY_DEFINITION: dict[str, tuple[list[str], Literal["*", "*1", "1*", "1"]]] = {
    "source": (["altid", "pid", "pref", "mediatype"], "*"),
    "kind": ([], "*1"),
    "fn": (["language", "altid", "pid", "pref", "type"], "1*"),
    "n": (["language", "altid", "sort-as"], "*1"),
    "nickname": (["language", "altid", "pid", "pref", "type"], "*"),
    "photo": (["altid", "pid", "pref", "type", "mediatype"], "*"),
    "bday": (["altid", "calscale"], "*1"),
    "anniversary": (["altid", "calscale"], "*1"),
    "gender": ([], "*1"),
    "adr": (["language", "altid", "pid", "pref", "type", "geo", "tz", "label"], "*"),
    "tel": (["altid", "pid", "pref", "type", "mediatype"], "*"),
    "email": (["altid", "pid", "pref", "type"], "*"),
    "impp": (["altid", "pid", "pref", "type", "mediatype"], "*"),
    "lang": (["altid", "pid", "pref", "type"], "*"),
    "tz": (["altid", "pid", "pref", "type", "mediatype"], "*"),
    "geo": (["altid", "pid", "pref", "type", "mediatype"], "*"),
    "title": (["language", "altid", "pid", "pref", "type"], "*"),
    "role": (["language", "altid", "pid", "pref", "type"], "*"),
    "logo": (["language", "altid", "pid", "pref", "type", "mediatype"], "*"),
    "org": (["language", "altid", "pid", "pref", "type", "sort-as"], "*"),
    "member": (["altid", "pid", "pref", "mediatype"], "*"),
    "related": (["altid", "pid", "pref", "type", "mediatype"], "*"),
    "categories": (["altid", "pid", "pref", "type"], "*"),
    "note": (["language", "altid", "pid", "pref", "type"], "*"),
    "prodid": ([], "*1"),
    "rev": ([], "*1"),
    "sound": (["language", "altid", "pid", "pref", "type", "mediatype"], "*"),
    "uid": ([], "*1"),
    "clientpidmap": ([], "*"),
    "url": (["altid", "pid", "pref", "type", "mediatype"], "*"),
    "key": (["altid", "pid", "pref", "type", "mediatype"], "*"),
    "fburl": (["altid", "pid", "pref", "type", "mediatype"], "*"),
    "caladruri": (["altid", "pid", "pref", "type", "mediatype"], "*"),
    "caluri": (["altid", "pid", "pref", "type", "mediatype"], "*"),
}


PROPERTY_VALUE_TYPES = {
    "bday": ["date", "time", "date-time", "text"],
    "anniversary": ["date", "time", "date-time", "text"],
    "key": ["text", "uri"],
    "tel": ["uri", "text"],
    "tz": ["text", "uri", "utc-offset"],
    "related": ["text", "uri"],
}


def get_data_from_children(node: Node, child_name: str) -> list[str]:
    values: list[str] = []
    child_nodes = node.getTags(child_name)
    for child_node in child_nodes:
        child_value = child_node.getData()
        if child_value:
            values.append(child_value)
    return values


def add_children(node: Node, child_name: str, values: list[str]) -> None:
    for value in values:
        node.addChild(child_name, payload=value)


def get_multiple_type_value(node: Node, types: list[str]) -> tuple[str, str]:
    for type_ in types:
        value = node.getTagData(type_)
        if value:
            return type_, value

    raise ValueError("no value found")


def make_parameters(parameters: Parameters) -> Node:
    parameters_node = Node("parameters")
    for parameter in parameters.values():
        parameters_node.addChild(node=parameter.to_node())
    return parameters_node


def get_parameters(node: Node) -> Parameters:
    name = node.getName()
    definition = PROPERTY_DEFINITION[name]
    allowed_parameters = definition[0]
    parameters_node = node.getTag("parameters")
    if parameters_node is None:
        return Parameters()

    parameters: dict[str, Any] = {}
    for parameter in allowed_parameters:
        parameter_node = parameters_node.getTag(parameter)
        if parameter_node is None:
            continue

        parameter_class = PARAMETER_CLASSES.get(parameter_node.getName())
        if parameter_class is None:
            continue

        parameter = parameter_class.from_node(parameter_node)
        parameters[parameter.name] = parameter

    return Parameters(parameters)


@dataclass
class Parameter:

    name: str
    type: str
    value: str

    @classmethod
    def from_node(cls, node: Node) -> Parameter:
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid parameter name: {name}")

        value = node.getTagData(cls.type)
        if not value:
            raise ValueError("no parameter value found")

        return cls(value)  # type: ignore

    def to_node(self) -> Node:
        node = Node(self.name)
        node.addChild(self.type, payload=self.value)
        return node

    def copy(self) -> Parameter:
        return self.__class__(value=self.value)  # type: ignore


@dataclass
class MultiParameter:

    name: str
    type: str
    values: set[str]

    @classmethod
    def from_node(cls, node: Node) -> MultiParameter:
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid parameter name: {name}")

        value_nodes = node.getTags(cls.type)
        if not value_nodes:
            raise ValueError("no parameter value found")

        values: set[str] = set()
        for value_node in value_nodes:
            value = value_node.getData()
            if value:
                values.add(value)

        if not values:
            raise ValueError("no parameter value found")

        return cls(values)  # type: ignore

    def to_node(self) -> Node:
        node = Node(self.name)
        for value in self.values:
            node.addChild(self.type, payload=value)
        return node

    def copy(self) -> MultiParameter:
        return self.__class__(values=set(self.values))  # type: ignore


@dataclass
class LanguageParameter(Parameter):

    name: str = field(default="language", init=False)
    type: str = field(default="language-tag", init=False)


@dataclass
class PrefParameter(Parameter):

    name: str = field(default="pref", init=False)
    type: str = field(default="integer", init=False)


@dataclass
class AltidParameter(Parameter):

    name: str = field(default="altid", init=False)
    type: str = field(default="text", init=False)


@dataclass
class PidParameter(MultiParameter):

    name: str = field(default="pid", init=False)
    type: str = field(default="text", init=False)


@dataclass
class TypeParameter(MultiParameter):

    name: str = field(default="type", init=False)
    type: str = field(default="text", init=False)


@dataclass
class MediatypeParameter(Parameter):

    name: str = field(default="mediatype", init=False)
    type: str = field(default="text", init=False)


@dataclass
class CalscaleParameter(Parameter):

    name: str = field(default="calscale", init=False)
    type: str = field(default="text", init=False)


@dataclass
class SortasParameter(MultiParameter):

    name: str = field(default="sort-as", init=False)
    type: str = field(default="text", init=False)


@dataclass
class GeoParameter(Parameter):

    name: str = field(default="geo", init=False)
    type: str = field(default="uri", init=False)


@dataclass
class TzParameter:

    name: str = field(default="tz", init=False)
    value_type: str
    value: str

    @classmethod
    def from_node(cls, node: Node) -> TzParameter:
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid property name: {name}")

        value_type, value = get_multiple_type_value(node, ["text", "uri"])
        return cls(value_type, value)

    def to_node(self) -> Node:
        node = Node(self.name)
        node.addChild(self.value_type, payload=self.value)
        return node

    def copy(self) -> TzParameter:
        return self.__class__(value_type=self.value_type, value=self.value)


class Parameters:
    def __init__(
        self,
        parameters: dict[str, Parameter | MultiParameter | TzParameter] | None = None,
    ) -> None:
        if parameters is None:
            parameters = {}
        self._parameters = parameters

    def values(self) -> ValuesView[Parameter | MultiParameter | TzParameter]:
        return self._parameters.values()

    def get_types(self) -> set[str]:
        parameter = self._parameters.get("type")
        if parameter is None:
            return set()

        assert isinstance(parameter, TypeParameter)
        return parameter.values

    def remove_types(self, types: list[str]) -> None:
        parameter = self._parameters.get("type")
        if parameter is None:
            raise ValueError("no type parameter")

        assert isinstance(parameter, TypeParameter)
        for type_ in types:
            parameter.values.discard(type_)

        if not parameter.values:
            self._parameters.pop("type")

    def add_types(self, types: list[str]) -> None:
        parameter = self._parameters.get("type")
        if parameter is None:
            parameter = TypeParameter(set(types))
            self._parameters["type"] = parameter
            return

        assert isinstance(parameter, TypeParameter)
        parameter.values.update(types)

    def copy(self) -> Parameters:
        parameters: dict[str, Parameter | MultiParameter | TzParameter] = {}
        for name, parameter in self._parameters.items():
            parameters[name] = parameter.copy()
        return self.__class__(parameters=parameters)


PARAMETER_CLASSES = {
    "language": LanguageParameter,
    "pref": PrefParameter,
    "altid": AltidParameter,
    "pid": PidParameter,
    "type": TypeParameter,
    "mediatype": MediatypeParameter,
    "calscale": CalscaleParameter,
    "sort-as": SortasParameter,
    "geo": GeoParameter,
    "tz": TzParameter,
}


@dataclass
class UriProperty:

    name: str
    value: str
    parameters: Parameters = field(default_factory=Parameters)

    @classmethod
    def from_node(cls, node: Node) -> UriProperty:
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid property name: {name}")

        value = node.getTagData("uri")
        if not value:
            raise ValueError("no value found")

        parameters = get_parameters(node)

        return cls(value, parameters)  # type: ignore

    def to_node(self) -> Node:
        node = Node(self.name)
        if self.parameters:
            node.addChild(node=make_parameters(self.parameters))
        node.addChild("uri", payload=self.value)  # type: ignore
        return node

    @property
    def is_empty(self) -> bool:
        return not self.value

    def copy(self) -> UriProperty:
        return self.__class__(
            value=self.value, parameters=self.parameters.copy()
        )  # type: ignore


@dataclass
class TextProperty:

    name: str
    value: str
    parameters: Parameters = field(default_factory=Parameters)

    @classmethod
    def from_node(cls, node: Node) -> TelProperty:
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid property name: {name}")

        text = node.getTagData("text")
        if not text:
            raise ValueError("no value found")

        parameters = get_parameters(node)

        return cls(text, parameters)  # type: ignore

    def to_node(self) -> Node:
        node = Node(self.name)
        if self.parameters:
            node.addChild(node=make_parameters(self.parameters))
        node.addChild("text", payload=self.value)
        return node

    @property
    def is_empty(self) -> bool:
        return not self.value

    def copy(self) -> TextProperty:
        return self.__class__(
            value=self.value, parameters=self.parameters.copy()
        )  # type: ignore


@dataclass
class TextListProperty:

    name: str
    values: list[str]
    parameters: Parameters = field(default_factory=Parameters)

    @classmethod
    def from_node(cls, node: Node) -> TextListProperty:
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid property name: {name}")

        text_nodes = node.getTags("text")
        if not text_nodes:
            raise ValueError("no value found")

        values = get_data_from_children(node, "text")
        if not values:
            raise ValueError("no values found")

        parameters = get_parameters(node)

        return cls(values, parameters)  # type: ignore

    def to_node(self) -> Node:
        node = Node(self.name)
        if self.parameters:
            node.addChild(node=make_parameters(self.parameters))
        add_children(node, "text", self.values)
        return node

    @property
    def is_empty(self) -> bool:
        return not self.values

    def copy(self) -> TextListProperty:
        return self.__class__(
            values=list(self.values), parameters=self.parameters.copy()
        )  # type: ignore


@dataclass
class MultipleValueProperty:

    name: str
    value_type: str
    value: str
    parameters: Parameters = field(default_factory=Parameters)

    @classmethod
    def from_node(cls, node: Node) -> MultipleValueProperty:
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid property name: {name}")

        types = PROPERTY_VALUE_TYPES[cls.name]
        value_type, value = get_multiple_type_value(node, types)

        parameters = get_parameters(node)

        return cls(value_type, value, parameters)  # type: ignore

    def to_node(self) -> Node:
        node = Node(self.name)
        if self.parameters:
            node.addChild(node=make_parameters(self.parameters))
        node.addChild(self.value_type, payload=self.value)
        return node

    @property
    def is_empty(self) -> bool:
        return not self.value

    def copy(self) -> MultipleValueProperty:
        return self.__class__(
            value_type=self.value_type,
            value=self.value,
            parameters=self.parameters.copy(),
        )  # type: ignore


@dataclass
class SourceProperty(UriProperty):

    name: str = field(default="source", init=False)


@dataclass
class KindProperty(TextProperty):

    name: str = field(default="kind", init=False)

    @classmethod
    def from_node(cls, node: Node) -> KindProperty:  # type: ignore
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid property name: {name}")

        text = node.getTagData("text")
        if not text:
            raise ValueError("no value found")

        if text not in ALLOWED_KIND_VALUES:
            text = "individual"

        parameters = get_parameters(node)

        return cls(text, parameters)


@dataclass
class FnProperty(TextProperty):

    name: str = field(default="fn", init=False)


@dataclass
class NProperty:

    name: str = field(default="n", init=False)
    surname: list[str] = field(default_factory=list)
    given: list[str] = field(default_factory=list)
    additional: list[str] = field(default_factory=list)
    prefix: list[str] = field(default_factory=list)
    suffix: list[str] = field(default_factory=list)
    parameters: Parameters = field(default_factory=Parameters)

    @classmethod
    def from_node(cls, node: Node) -> NProperty:
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid property name: {name}")

        surname = get_data_from_children(node, "surname")
        given = get_data_from_children(node, "given")
        additional = get_data_from_children(node, "additional")
        prefix = get_data_from_children(node, "prefix")
        suffix = get_data_from_children(node, "suffix")

        parameters = get_parameters(node)

        return cls(surname, given, additional, prefix, suffix, parameters)

    def to_node(self) -> Node:
        node = Node(self.name)
        if self.parameters:
            node.addChild(node=make_parameters(self.parameters))
        add_children(node, "surname", self.surname)
        add_children(node, "given", self.given)
        add_children(node, "additional", self.additional)
        add_children(node, "prefix", self.prefix)
        add_children(node, "suffix", self.suffix)
        return node

    @property
    def is_empty(self) -> bool:
        return not (
            self.surname or self.given or self.additional or self.suffix or self.prefix
        )

    def copy(self) -> NProperty:
        return self.__class__(
            surname=list(self.surname),
            given=list(self.given),
            additional=list(self.additional),
            prefix=list(self.prefix),
            suffix=list(self.suffix),
            parameters=self.parameters.copy(),
        )


@dataclass
class NicknameProperty(TextListProperty):

    name: str = field(default="nickname", init=False)


@dataclass
class PhotoProperty(UriProperty):

    name: str = field(default="photo", init=False)


@dataclass
class BDayProperty(MultipleValueProperty):

    name: str = field(default="bday", init=False)


@dataclass
class AnniversaryProperty(MultipleValueProperty):

    name: str = field(default="anniversary", init=False)


@dataclass
class GenderProperty:

    name: str = field(default="gender", init=False)
    sex: str | None = None
    identity: str | None = None
    parameters: Parameters = field(default_factory=Parameters)

    @classmethod
    def from_node(cls, node: Node) -> GenderProperty:
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid property name: {name}")

        sex = node.getTagData("sex")
        if sex not in ALLOWED_SEX_VALUES:
            sex = None

        identity = node.getTagData("identity")
        if not identity:
            identity = None

        parameters = get_parameters(node)

        return cls(sex, identity, parameters)

    def to_node(self) -> Node:
        node = Node(self.name)
        if self.parameters:
            node.addChild(node=make_parameters(self.parameters))
        if self.sex:
            node.addChild("sex", payload=self.sex)
        if self.identity:
            node.addChild("identity", payload=self.identity)
        return node

    @property
    def is_empty(self) -> bool:
        return not (self.sex or self.identity)

    def copy(self) -> GenderProperty:
        return self.__class__(
            sex=self.sex, identity=self.identity, parameters=self.parameters.copy()
        )


@dataclass
class AdrProperty:

    name: str = field(default="adr", init=False)
    pobox: list[str] = field(default_factory=list)
    ext: list[str] = field(default_factory=list)
    street: list[str] = field(default_factory=list)
    locality: list[str] = field(default_factory=list)
    region: list[str] = field(default_factory=list)
    code: list[str] = field(default_factory=list)
    country: list[str] = field(default_factory=list)
    parameters: Parameters = field(default_factory=Parameters)

    @classmethod
    def from_node(cls, node: Node) -> AdrProperty:
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid property name: {name}")

        pobox = get_data_from_children(node, "pobox")
        ext = get_data_from_children(node, "ext")
        street = get_data_from_children(node, "street")
        locality = get_data_from_children(node, "locality")
        region = get_data_from_children(node, "region")
        code = get_data_from_children(node, "code")
        country = get_data_from_children(node, "country")

        parameters = get_parameters(node)

        return cls(pobox, ext, street, locality, region, code, country, parameters)

    def to_node(self) -> Node:
        node = Node(self.name)
        if self.parameters:
            node.addChild(node=make_parameters(self.parameters))
        add_children(node, "pobox", self.pobox)
        add_children(node, "ext", self.ext)
        add_children(node, "street", self.street)
        add_children(node, "locality", self.locality)
        add_children(node, "region", self.region)
        add_children(node, "code", self.code)
        add_children(node, "country", self.country)
        return node

    @property
    def is_empty(self) -> bool:
        return not (
            self.pobox
            or self.ext
            or self.street
            or self.locality
            or self.region
            or self.code
            or self.country
        )

    def copy(self) -> AdrProperty:
        return self.__class__(
            pobox=list(self.pobox),
            ext=list(self.ext),
            street=list(self.street),
            locality=list(self.locality),
            region=list(self.region),
            code=list(self.code),
            country=list(self.country),
            parameters=self.parameters.copy(),
        )


@dataclass
class TelProperty(MultipleValueProperty):

    name: str = field(default="tel", init=False)


@dataclass
class EmailProperty(TextProperty):

    name: str = field(default="email", init=False)


@dataclass
class ImppProperty(UriProperty):

    name: str = field(default="impp", init=False)


@dataclass
class LangProperty:

    name: str = field(default="lang", init=False)
    value: str
    parameters: Parameters = field(default_factory=Parameters)

    @classmethod
    def from_node(cls, node: Node) -> LangProperty:
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid property name: {name}")

        value = node.getTagData("language-tag")
        if not value:
            raise ValueError("no value found")

        parameters = get_parameters(node)

        return cls(value, parameters)

    def to_node(self) -> Node:
        node = Node(self.name)
        if self.parameters:
            node.addChild(node=make_parameters(self.parameters))
        node.addChild("language-tag", payload=self.value)
        return node

    @property
    def is_empty(self) -> bool:
        return not self.value

    def copy(self) -> LangProperty:
        return self.__class__(value=self.value, parameters=self.parameters.copy())


@dataclass
class TzProperty(MultipleValueProperty):

    name: str = field(default="tz", init=False)


@dataclass
class GeoProperty(UriProperty):

    name: str = field(default="geo", init=False)


@dataclass
class TitleProperty(TextProperty):

    name: str = field(default="title", init=False)


@dataclass
class RoleProperty(TextProperty):

    name: str = field(default="role", init=False)


@dataclass
class LogoProperty(UriProperty):

    name: str = field(default="logo", init=False)


@dataclass
class OrgProperty(TextListProperty):

    name: str = field(default="org", init=False)


@dataclass
class MemberProperty(UriProperty):

    name: str = field(default="member", init=False)


@dataclass
class RelatedProperty(MultipleValueProperty):

    name: str = field(default="related", init=False)


@dataclass
class CategoriesProperty(TextListProperty):

    name: str = field(default="categories", init=False)


@dataclass
class NoteProperty(TextProperty):

    name: str = field(default="note", init=False)


@dataclass
class ProdidProperty(TextProperty):

    name: str = field(default="prodid", init=False)


@dataclass
class RevProperty(TextProperty):

    name: str = field(default="rev", init=False)

    @classmethod
    def from_node(cls, node: Node) -> RevProperty:  # type: ignore
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid property name: {name}")

        timestamp = node.getTagData("timestamp")
        if not timestamp:
            raise ValueError("no value found")

        parameters = get_parameters(node)

        return cls(timestamp, parameters)

    def to_node(self) -> Node:
        node = Node(self.name)
        if self.parameters:
            node.addChild(node=make_parameters(self.parameters))
        node.addChild("timestamp", payload=self.value)
        return node


@dataclass
class SoundProperty(UriProperty):

    name: str = field(default="sound", init=False)


@dataclass
class UidProperty(UriProperty):

    name: str = field(default="uid", init=False)


@dataclass
class ClientpidmapProperty:

    name: str = field(default="clientpidmap", init=False)
    sourceid: int
    uri: str
    parameters: Parameters = field(default_factory=Parameters)

    @classmethod
    def from_node(cls, node: Node) -> ClientpidmapProperty:
        name = node.getName()
        if name != cls.name:
            raise ValueError(f"invalid property name: {name}")

        sourceid = node.getTagData("sourceid")
        if not sourceid:
            raise ValueError("no value found")

        uri = node.getTagData("uri")
        if not uri:
            raise ValueError("no value found")

        parameters = get_parameters(node)

        return cls(sourceid, uri, parameters)

    def to_node(self) -> Node:
        node = Node(self.name)
        if self.parameters:
            node.addChild(node=make_parameters(self.parameters))
        node.addChild("sourceid", payload=self.sourceid)
        node.addChild("uri", payload=self.uri)
        return node

    @property
    def is_empty(self) -> bool:
        return not self.uri

    def copy(self) -> ClientpidmapProperty:
        return self.__class__(
            sourceid=self.sourceid, uri=self.uri, parameters=self.parameters.copy()
        )


@dataclass
class UrlProperty(UriProperty):

    name: str = field(default="url", init=False)


@dataclass
class KeyProperty(MultipleValueProperty):

    name: str = field(default="key", init=False)


@dataclass
class FBurlProperty(UriProperty):

    name: str = field(default="fburl", init=False)


@dataclass
class CaladruriProperty(UriProperty):

    name: str = field(default="caladruri", init=False)


@dataclass
class CaluriProperty(UriProperty):

    name: str = field(default="calurl", init=False)


PROPERTY_CLASSES = {
    "source": SourceProperty,
    "kind": KindProperty,
    "fn": FnProperty,
    "n": NProperty,
    "nickname": NicknameProperty,
    "photo": PhotoProperty,
    "bday": BDayProperty,
    "anniversary": AnniversaryProperty,
    "gender": GenderProperty,
    "adr": AdrProperty,
    "tel": TelProperty,
    "email": EmailProperty,
    "impp": ImppProperty,
    "lang": LangProperty,
    "tz": TzProperty,
    "geo": GeoProperty,
    "title": TitleProperty,
    "role": RoleProperty,
    "logo": LogoProperty,
    "org": OrgProperty,
    "member": MemberProperty,
    "related": RelatedProperty,
    "categories": CategoriesProperty,
    "note": NoteProperty,
    "prodid": ProdidProperty,
    "rev": RevProperty,
    "sound": SoundProperty,
    "uid": UidProperty,
    "clientpidmap": ClientpidmapProperty,
    "url": UrlProperty,
    "key": KeyProperty,
    "fburl": FBurlProperty,
    "caladruri": CaladruriProperty,
    "caluri": CaluriProperty,
}

PropertyT = (
    SourceProperty
    | KindProperty
    | FnProperty
    | NProperty
    | NicknameProperty
    | PhotoProperty
    | BDayProperty
    | AnniversaryProperty
    | GenderProperty
    | AdrProperty
    | TelProperty
    | EmailProperty
    | ImppProperty
    | LangProperty
    | TzProperty
    | GeoProperty
    | TitleProperty
    | RoleProperty
    | LogoProperty
    | OrgProperty
    | MemberProperty
    | RelatedProperty
    | CategoriesProperty
    | NoteProperty
    | ProdidProperty
    | RevProperty
    | SoundProperty
    | UidProperty
    | ClientpidmapProperty
    | UrlProperty
    | KeyProperty
    | FBurlProperty
    | CaladruriProperty
    | CaluriProperty
)


def get_property_from_name(name: str, node: Node) -> PropertyT | None:
    property_class = PROPERTY_CLASSES.get(name)
    if property_class is None:
        return None

    try:
        return property_class.from_node(node)
    except Exception as error:
        log.warning("invalid vcard property: %s %s", error, node)
        return None


VCardPropertiesT = list[tuple[str | None, PropertyT | list[PropertyT]]]


class VCard:
    def __init__(self, properties: VCardPropertiesT | None = None) -> None:
        if properties is None:
            properties = []
        self._properties = properties

    @classmethod
    def from_node(cls, node: Node) -> VCard:
        properties: VCardPropertiesT = []
        for child in node.getChildren():
            child_name = child.getName()

            if child_name == "group":
                group_name = child.getAttr("name")
                if not group_name:
                    continue

                group_properties: list[PropertyT] = []
                for group_child in child.getChildren():
                    group_child_name = group_child.getName()
                    property_ = get_property_from_name(group_child_name, group_child)
                    if property_ is None:
                        continue
                    group_properties.append(property_)

                properties.append((group_name, group_properties))

            else:

                property_ = get_property_from_name(child_name, child)
                if property_ is None:
                    continue
                properties.append((None, property_))

        return cls(properties)

    def to_node(self) -> Node:
        vcard = Node(f"{Namespace.VCARD4} vcard")
        for group, props in self._properties:
            if group is None:
                assert not isinstance(props, list)
                vcard.addChild(node=props.to_node())
            else:
                group = Node(group)
                assert isinstance(props, list)
                for prop in props:
                    group.addChild(node=prop.to_node())
                vcard.addChild(node=group)
        return vcard

    def get_properties(self) -> list[PropertyT]:
        properties: list[PropertyT] = []
        for group, props in self._properties:
            if group is None:
                assert not isinstance(props, list)
                properties.append(props)
            else:
                assert isinstance(props, list)
                properties.extend(props)
        return properties

    def add_property(self, name: str, *args: Any, **kwargs: Any):
        prop = PROPERTY_CLASSES.get(name)(*args, **kwargs)
        self._properties.append((None, prop))
        return prop

    def remove_property(self, prop: PropertyT) -> None:
        for _group, props in list(self._properties):
            if isinstance(props, list):
                if prop in props:
                    props.remove(prop)
                    return

            elif prop is props:
                self._properties.remove((None, props))
                return

        raise ValueError("prop not found in vcard")

    def copy(self) -> VCard:
        properties: VCardPropertiesT = []
        for group_name, props in self._properties:
            if group_name is None:
                assert not isinstance(props, list)
                properties.append((None, props.copy()))
            else:
                assert isinstance(props, list)
                group_properties = [prop.copy() for prop in props]
                properties.append((group_name, group_properties))
        return self.__class__(properties=properties)


class VCard4(BaseModule):

    _depends = {
        "publish": "PubSub",
        "request_items": "PubSub",
    }

    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def request_vcard(self, jid: JID | None = None):
        task = yield

        items = yield self.request_items(Namespace.VCARD4_PUBSUB, jid=jid, max_items=1)

        raise_if_error(items)

        if not items:
            yield task.set_result(None)

        yield _get_vcard(items[0])

    @iq_request_task
    def set_vcard(self, vcard: VCard, public: bool = False):
        task = yield

        access_model = "open" if public else "presence"

        options = {
            "pubsub#persist_items": "true",
            "pubsub#access_model": access_model,
        }

        result = yield self.publish(
            Namespace.VCARD4_PUBSUB,
            vcard.to_node(),
            id_="current",
            options=options,
            force_node_options=True,
        )

        yield finalize(task, result)


def _get_vcard(item: Node) -> VCard:
    vcard = item.getTag("vcard", namespace=Namespace.VCARD4)
    if vcard is None:
        raise MalformedStanzaError("vcard node missing", item)

    try:
        vcard = VCard.from_node(vcard)
    except Exception as error:
        raise MalformedStanzaError("invalid vcard: %s" % error, item)

    return vcard
