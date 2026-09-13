# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import typing

import dataclasses
from abc import ABC
from abc import abstractmethod
from dataclasses import _MISSING_TYPE
from dataclasses import MISSING

from lxml import etree

from . import types

ETreeElementT = etree._Element  # type: ignore

XML_DATA_TYPE_CONVERTERS = {
    int: types.Integer,
    float: types.Float,
    str: types.String,
    bool: types.Bool,
}

ValueTypeT = int | float | str | bool


class XMLNode:
    TAG: typing.ClassVar[tuple[str, str]] = ("", "")

    @classmethod
    def from_element(cls, element: ETreeElementT):
        values = {}
        for field in dataclasses.fields(cls):
            parser = typing.cast(PropParser, field.metadata.get("parser"))
            parser.set_type(field.type)
            values[field.name] = parser.deserialize(element, field.name)

        return cls(**values)

    def to_element(self) -> ETreeElementT:
        element = etree.Element(self.TAG[0])
        for field in dataclasses.fields(self):
            parser = typing.cast(PropParser, field.metadata.get("parser"))
            parser.set_type(field.type)
            parser.serialize(element, field.name, getattr(self, field.name))

        return element


class PropParser(ABC):
    def set_type(self, type: typing.Any) -> None:
        xml_data_type = XML_DATA_TYPE_CONVERTERS.get(type)
        if xml_data_type is not None:
            self._xml_data_type = xml_data_type

    @abstractmethod
    def deserialize(self, element: ETreeElementT, name: str) -> typing.Any:
        raise NotImplementedError

    @abstractmethod
    def serialize(self, element: ETreeElementT, name: str, value: typing.Any) -> None:
        raise NotImplementedError


class XMLAttrValue(PropParser):
    def __init__(self, required: bool, default: typing.Any | _MISSING_TYPE) -> None:
        self._required = required
        self._default = default

    def deserialize(self, element: ETreeElementT, name: str) -> ValueTypeT | None:
        attr = element.get(name)
        if attr is None:
            if self._required:
                raise ValueError(f"missing attr {name}")

            if self._default is MISSING:
                return None

            return self._default
        return self._xml_data_type.deserialize(attr)

    def serialize(
        self, element: ETreeElementT, name: str, value: ValueTypeT | None
    ) -> None:
        if value is None:
            return
        element.set(name, self._xml_data_type.serialize(value))


class XMLChild(PropParser):
    def __init__(self, required: bool) -> None:
        self._required = required

    def set_type(self, type: type[XMLNode]) -> None:
        self._child = type

    def deserialize(self, element: ETreeElementT, name: str) -> XMLNode | None:
        tag, _namespace = self._child.TAG
        node = element.find(tag)
        if node is None:
            if self._required:
                raise ValueError("missing child")
            return None

        assert node is not None
        return self._child.from_element(node)

    def serialize(
        self, element: ETreeElementT, name: str, value: XMLNode | None
    ) -> None:
        if value is None:
            return
        element.append(value.to_element())


class XMLChildList(PropParser):
    def __init__(self) -> None:
        self._xml_node_classes: dict[tuple[str, str], XMLNode] = {}

    def set_type(self, type: typing.Any) -> None:
        if typing.get_origin(type) is not list:
            raise ValueError("ChildList must have a list[] annotation")

        arg = typing.get_args(type)[0]
        for xml_node_cls in typing.get_args(arg):
            self._xml_node_classes[xml_node_cls.TAG] = xml_node_cls

    def deserialize(self, element: ETreeElementT, name: str) -> list[XMLNode]:
        nodes: list[XMLNode] = []
        for sub in element:
            xml_node_cls = self._xml_node_classes.get((sub.tag, ""))
            if xml_node_cls is None:
                continue
            xml_node = xml_node_cls.from_element(sub)
            nodes.append(xml_node)
        return nodes

    def serialize(
        self, element: ETreeElementT, name: str, value: list[XMLNode]
    ) -> None:
        for xml_node in value:
            element.append(xml_node.to_element())


class XMLChildText(PropParser):
    def __init__(self, required: bool, default: typing.Any | _MISSING_TYPE) -> None:
        self._required = required
        self._default = default

    def deserialize(self, element: ETreeElementT, name: str) -> ValueTypeT | None:
        node = element.find(name)
        if node is None or not node.text:
            if self._required:
                raise ValueError("missing child value")
            return None

        return self._xml_data_type.deserialize(node.text)

    def serialize(
        self, element: ETreeElementT, name: str, value: ValueTypeT | None
    ) -> None:
        if value is None:
            return
        subelement = etree.SubElement(element, name)
        subelement.text = self._xml_data_type.serialize(value)


class XMLChildFlag(PropParser):
    def __init__(self, required: bool, default: bool = False) -> None:
        self._required = required
        self._default = default

    def deserialize(self, element: ETreeElementT, name: str) -> bool:
        node = element.find(name)
        if node is None:
            if self._required:
                raise ValueError("missing child")
            return self._default
        return True

    def serialize(self, element: ETreeElementT, name: str, value: ValueTypeT) -> None:
        if not value:
            return
        etree.SubElement(element, name)


class ChildConverter(typing.Protocol):
    def get_xml_node_cls(self) -> typing.Any:
        return NotImplementedError

    def deserialize(self, element: XMLNode) -> typing.Any:
        raise NotImplementedError

    def serialize(self, element: ETreeElementT, value: typing.Any) -> None:
        raise NotImplementedError


class ChildAttrGetter(ChildConverter):
    def __init__(self, obj: type[XMLNode], attr: str) -> None:
        self._obj = obj
        self._attr = attr

    def get_xml_node_cls(self) -> typing.Any:
        return self._obj

    def deserialize(self, element: typing.Any) -> typing.Any:
        return getattr(element, self._attr)

    def serialize(self, element: ETreeElementT, value: typing.Any) -> None:
        subelement = etree.SubElement(element, self._obj.TAG[0])
        for field in dataclasses.fields(self._obj):
            if field.name == self._attr:
                parser = typing.cast(PropParser, field.metadata.get("parser"))
                parser.set_type(field.type)
                parser.serialize(subelement, field.name, value)
                break


class XMLChildValue(PropParser):
    def __init__(
        self,
        child_converter: ChildConverter,
        required: bool = False,
    ) -> None:
        self._required = required
        self._child_converter = child_converter

    def deserialize(self, element: ETreeElementT, name: str) -> ValueTypeT | None:
        name = self._child_converter.get_xml_node_cls().TAG[0]

        node = element.find(name)
        if node is None:
            if self._required:
                raise ValueError("missing child values")
            return None

        xml_node = self._child_converter.get_xml_node_cls().from_element(node)
        return self._child_converter.deserialize(xml_node)

    def serialize(
        self, element: ETreeElementT, name: str, value: ValueTypeT | None
    ) -> None:
        if value is None:
            return
        self._child_converter.serialize(element, value)


class XMLChildValueList(PropParser):
    def __init__(
        self,
        child_converter: ChildConverter,
        required: bool = False,
    ) -> None:
        self._required = required
        self._child_converter = child_converter

    def set_type(self, type: typing.Any) -> None:
        self._container_type = typing.get_origin(type)

    def deserialize(self, element: ETreeElementT, name: str) -> list[ValueTypeT]:
        container = self._container_type()
        try:
            container_add_method = container.add
        except AttributeError:
            container_add_method = container.append

        name = self._child_converter.get_xml_node_cls().TAG[0]

        nodes = element.findall(name)
        if not nodes:
            if self._required:
                raise ValueError("missing child values")
            return nodes

        for node in nodes:
            xml_element = self._child_converter.get_xml_node_cls().from_element(node)
            value = self._child_converter.deserialize(xml_element)
            container_add_method(value)

        return container

    def serialize(
        self, element: ETreeElementT, name: str, value: list[ValueTypeT]
    ) -> None:
        for v in value:
            self._child_converter.serialize(element, v)


def AttrValue(
    default: typing.Any | _MISSING_TYPE = MISSING, required: bool = False
) -> typing.Any:
    return dataclasses.field(
        default=default, metadata={"parser": XMLAttrValue(required, default)}
    )


def Child(required: bool = False) -> typing.Any:
    return dataclasses.field(metadata={"parser": XMLChild(required)})


def ChildList() -> typing.Any:
    return dataclasses.field(metadata={"parser": XMLChildList()})


def ChildText(
    default: typing.Any | _MISSING_TYPE = MISSING, required: bool = False
) -> typing.Any:
    return dataclasses.field(
        default=default, metadata={"parser": XMLChildText(required, default)}
    )


def ChildValue(child_converter: ChildConverter, required: bool = False) -> typing.Any:
    return dataclasses.field(
        metadata={"parser": XMLChildValue(child_converter, required)}
    )


def ChildValueList(
    child_converter: ChildConverter, required: bool = False
) -> typing.Any:
    return dataclasses.field(
        metadata={"parser": XMLChildValueList(child_converter, required)}
    )


def ChildFlag(default: bool = False, required: bool = False) -> typing.Any:
    return dataclasses.field(metadata={"parser": XMLChildFlag(required, default)})


@typing.dataclass_transform(
    field_specifiers=(
        AttrValue,
        Child,
        ChildList,
        ChildText,
        ChildValue,
        ChildValueList,
        ChildFlag,
    )
)
def xml_model(f: typing.Type[typing.Any]):
    return dataclasses.dataclass(f)
