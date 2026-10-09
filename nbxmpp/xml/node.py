# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import typing

import dataclasses
import logging
from abc import ABC
from abc import abstractmethod
from contextvars import ContextVar
from dataclasses import _MISSING_TYPE
from dataclasses import MISSING
from types import NoneType
from types import UnionType

from lxml import etree

from nbxmpp.protocol import JID
from nbxmpp.types import ETreeElementT
from nbxmpp.util import determine_qname
from nbxmpp.util import QName

from . import types

T_ = typing.TypeVar("T_")


XML_DATA_TYPE_CONVERTERS = {
    int: types.Integer,
    int | None: types.Integer,
    float: types.Float,
    float | None: types.Float,
    str: types.String,
    str | None: types.String,
    bool: types.Bool,
    bool | None: types.Bool,
    JID: types.JID,
    JID | None: types.JID,
}

ValueTypeT = int | float | str | bool | JID

logger: ContextVar[logging.Logger] = ContextVar("logger")

logger.set(logging.Logger("test"))


def tostring(element: ETreeElementT, pretty_print: bool = False) -> str:
    etree.indent(element, space="  ")
    return etree.tostring(element, pretty_print=pretty_print).decode()


def find_toplevel(element: ETreeElementT) -> ETreeElementT:
    toplevel = element
    for e in element.iterancestors():
        if e.getparent() is not None:
            toplevel = element
    return toplevel


def toplevel_to_string(element: ETreeElementT) -> str:
    return tostring(find_toplevel(element))


class XMLNode:
    TAG: typing.ClassVar[etree.QName]

    @classmethod
    def from_xml(cls: type[T_], xml: str) -> T_:
        element = etree.XML(xml)
        return cls.from_element(element)

    def to_xml(self, pretty: bool = False) -> str:
        element = self.to_element()
        return etree.tostring(element, pretty_print=pretty).decode()

    @classmethod
    def from_element(cls: type[T_], element: ETreeElementT) -> T_:
        if etree.QName(element) != cls.TAG:
            raise ValueError(f"Tag {cls.TAG} does not match element {element.tag}")

        values = {}
        for field in dataclasses.fields(cls):
            parser = typing.cast(PropParser, field.metadata.get("parser"))
            parser.set_type(field.type)
            values[field.name] = parser.deserialize(element, field.name)

        return cls(**values)

    def to_element(self) -> ETreeElementT:
        element = etree.Element(self.TAG)
        for field in dataclasses.fields(self):
            parser = typing.cast(PropParser, field.metadata.get("parser"))
            parser.set_type(field.type)
            parser.serialize(element, field.name, getattr(self, field.name))

        return element


class PropParser(ABC):
    def set_type(self, type_: typing.Any) -> None:
        xml_data_type = XML_DATA_TYPE_CONVERTERS.get(type_)
        if xml_data_type is None:
            raise ValueError("No converter found")
        self._xml_data_type = xml_data_type

    @abstractmethod
    def deserialize(self, element: ETreeElementT, field_name: str) -> typing.Any:
        raise NotImplementedError

    @abstractmethod
    def serialize(
        self, element: ETreeElementT, field_name: str, value: typing.Any
    ) -> None:
        raise NotImplementedError


class XMLAttr(PropParser):
    def __init__(
        self, default: ValueTypeT | None | _MISSING_TYPE, qname: QName | None
    ) -> None:
        self._default = default
        self._qname = qname

    def deserialize(self, element: ETreeElementT, field_name: str) -> ValueTypeT | None:
        # Don't inherit namespace from element
        qname = determine_qname(None, self._qname, field_name)
        attr = element.get(qname.text)
        if attr is not None:
            try:
                return self._xml_data_type.deserialize(attr)
            except Exception:
                logger.get().warning(
                    "%s\nUnable to convert %r to %s",
                    toplevel_to_string(element),
                    attr,
                    self._xml_data_type,
                )

        if self._default is MISSING:
            raise ValueError(f"missing attr {qname}")
        return self._default

    def serialize(
        self, element: ETreeElementT, field_name: str, value: ValueTypeT | None
    ) -> None:
        if value is None:
            return
        qname = determine_qname(None, self._qname, field_name)
        element.set(qname.text, self._xml_data_type.serialize(value))


class XMLText(PropParser):
    def __init__(self, default: ValueTypeT | None | _MISSING_TYPE) -> None:
        self._default = default

    def deserialize(self, element: ETreeElementT, field_name: str) -> ValueTypeT | None:
        if text := element.text:
            try:
                return self._xml_data_type.deserialize(text)
            except Exception:
                logger.get().warning(
                    "%s\nUnable to convert %r to %s",
                    toplevel_to_string(element),
                    text,
                    self._xml_data_type,
                )

        if self._default is MISSING:
            raise ValueError("missing text")
        return self._default

    def serialize(
        self, element: ETreeElementT, field_name: str, value: ValueTypeT | None
    ) -> None:
        if value is None:
            return
        element.text = self._xml_data_type.serialize(value)


class XMLPathValue(PropParser):
    def __init__(self, default: ValueTypeT | None | _MISSING_TYPE, expr: str) -> None:
        self._default = default
        self._expr = expr

    def deserialize(self, element: ETreeElementT, field_name: str) -> ValueTypeT | None:
        values = element.xpath(self._expr)
        if not isinstance(values, list):
            raise ValueError(f"Unexpected return type: {values!r}")

        if len(values) > 1:
            raise ValueError(f"XPath expression returned multiple results: {values!r}")

        if values:
            try:
                return self._xml_data_type.deserialize(values[0])
            except Exception:
                logger.get().warning(
                    "%s\nUnable to convert %r to %s",
                    toplevel_to_string(element),
                    values[0],
                    self._xml_data_type,
                )

        if self._default is MISSING:
            raise ValueError(f"expr did not find a value {self._expr}")
        return self._default

    def serialize(
        self, element: ETreeElementT, field_name: str, value: ValueTypeT | None
    ) -> None:
        if value is None:
            return
        raise NotImplementedError("Unable to serialize PathValue")


class XMLChild(PropParser):
    def __init__(
        self, default: None | _MISSING_TYPE = MISSING, expr: str | None = None
    ) -> None:
        self._default = default
        self._expr = expr

    def set_type(self, type_: type[XMLNode] | UnionType) -> None:
        if not isinstance(type_, UnionType):
            self._child_cls = type_
            return

        for child_cls in typing.get_args(type_):
            if child_cls is not NoneType:
                self._child_cls = child_cls
                return

        raise ValueError(f"Unable to set type for XMLChild: {type_}")

    def deserialize(self, element: ETreeElementT, field_name: str) -> XMLNode | None:
        if self._expr is not None:
            nodes = element.xpath(self._expr)
            if not isinstance(nodes, list):
                raise ValueError(f"Unexpected return type: {nodes!r}")

            if len(nodes) > 1:
                raise ValueError(
                    f"XPath expression returned multiple results: {nodes!r}"
                )

            node = nodes[0] if nodes else None
        else:
            node = element.find(self._child_cls.TAG)

        if node is not None:
            try:
                return self._child_cls.from_element(node)
            except Exception:
                logger.get().exception("")
                logger.get().warning(
                    "%s\nUnable to parse %s to %s",
                    toplevel_to_string(element),
                    node.tag,
                    self._child_cls,
                )

        if self._default is MISSING:
            raise ValueError("missing child")
        return self._default

    def serialize(
        self, element: ETreeElementT, field_name: str, value: XMLNode | None
    ) -> None:
        if self._expr is not None:
            raise ValueError("Unable to serialize child with expression")

        if value is None:
            return

        element.append(value.to_element())


class XMLChildList(PropParser):
    def __init__(self) -> None:
        self._xml_node_classes: dict[str, XMLNode] = {}

    def set_type(self, type_: typing.Any) -> None:
        if typing.get_origin(type_) is not list:
            raise ValueError("ChildList must have a list[] annotation")

        arg = typing.get_args(type_)[0]
        for xml_node_cls in typing.get_args(arg):
            self._xml_node_classes[xml_node_cls.TAG] = xml_node_cls

    def deserialize(self, element: ETreeElementT, field_name: str) -> list[XMLNode]:
        nodes: list[XMLNode] = []
        for sub in element:
            xml_node_cls = self._xml_node_classes.get(sub.tag)
            if xml_node_cls is None:
                continue
            try:
                xml_node = xml_node_cls.from_element(sub)
            except Exception:
                logger.get().warning(
                    "%s\nUnable to parse %r to %s",
                    toplevel_to_string(element),
                    sub.tag,
                    xml_node_cls,
                )
                continue

            nodes.append(xml_node)
        return nodes

    def serialize(
        self, element: ETreeElementT, field_name: str, value: list[XMLNode]
    ) -> None:
        for xml_node in value:
            element.append(xml_node.to_element())


class XMLChildText(PropParser):
    def __init__(
        self,
        default: ValueTypeT | None | _MISSING_TYPE = MISSING,
        qname: QName | None = None,
    ) -> None:
        self._default = default
        self._qname = qname

    def deserialize(self, element: ETreeElementT, field_name: str) -> ValueTypeT | None:
        qname = determine_qname(element, self._qname, field_name)
        node = element.find(qname.text)
        if node is not None and node.text:
            try:
                return self._xml_data_type.deserialize(node.text)
            except Exception:
                logger.get().warning(
                    "%s\nUnable to convert %r to %s",
                    toplevel_to_string(element),
                    node.text,
                    self._xml_data_type,
                )

        if self._default is MISSING:
            raise ValueError("missing child value")
        return self._default

    def serialize(
        self, element: ETreeElementT, field_name: str, value: ValueTypeT | None
    ) -> None:
        if value is None:
            return
        qname = determine_qname(element, self._qname, field_name)
        subelement = etree.SubElement(element, qname)
        subelement.text = self._xml_data_type.serialize(value)


class XMLChildFlag(PropParser):
    def __init__(self, default: bool | _MISSING_TYPE, qname: QName | None) -> None:
        self._default = default
        self._qname = qname

    def deserialize(self, element: ETreeElementT, field_name: str) -> bool:
        qname = determine_qname(element, self._qname, field_name)
        node = element.find(qname.text)
        if node is None:
            if self._default is MISSING:
                raise ValueError("missing child")
            return self._default
        return True

    def serialize(
        self, element: ETreeElementT, field_name: str, value: ValueTypeT
    ) -> None:
        if not value:
            return
        qname = determine_qname(element, self._qname, field_name)
        etree.SubElement(element, qname)


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
        subelement = etree.SubElement(element, self._obj.TAG)
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
        default: ValueTypeT | None | _MISSING_TYPE = MISSING,
    ) -> None:
        self._child_converter = child_converter
        self._default = default

    def deserialize(self, element: ETreeElementT, name: str) -> ValueTypeT | None:
        tag = self._child_converter.get_xml_node_cls().TAG

        node = element.find(tag)
        if node is None:
            if self._default is MISSING:
                raise ValueError("missing child values")
            return self._default

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

    def set_type(self, type_: typing.Any) -> None:
        self._container_type = typing.get_origin(type_)

    def deserialize(self, element: ETreeElementT, name: str) -> list[ValueTypeT]:
        container = self._container_type()
        try:
            container_add_method = container.add
        except AttributeError:
            container_add_method = container.append

        tag = self._child_converter.get_xml_node_cls().TAG

        nodes = element.findall(tag)
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


@typing.overload
def Text(*, default: bool) -> bool: ...
@typing.overload
def Text(*, default: str) -> str: ...
@typing.overload
def Text(*, default: int) -> int: ...
@typing.overload
def Text(*, default: float) -> float: ...
@typing.overload
def Text(*, default: JID) -> JID: ...
@typing.overload
def Text(*, default: None) -> typing.Any | None: ...
@typing.overload
def Text(*, default: _MISSING_TYPE = ...) -> typing.Any: ...
def Text(*, default: ValueTypeT | None | _MISSING_TYPE = MISSING) -> typing.Any | None:
    return dataclasses.field(default=default, metadata={"parser": XMLText(default)})


@typing.overload
def Attr(*, default: bool, qname: QName | None = ...) -> bool: ...
@typing.overload
def Attr(*, default: str, qname: QName | None = ...) -> str: ...
@typing.overload
def Attr(*, default: int, qname: QName | None = ...) -> int: ...
@typing.overload
def Attr(*, default: float, qname: QName | None = ...) -> float: ...
@typing.overload
def Attr(*, default: JID, qname: QName | None = ...) -> JID: ...
@typing.overload
def Attr(*, default: None, qname: QName | None = ...) -> typing.Any | None: ...
@typing.overload
def Attr(*, default: _MISSING_TYPE = ..., qname: QName | None = ...) -> typing.Any: ...
def Attr(
    *,
    default: ValueTypeT | None | _MISSING_TYPE = MISSING,
    qname: QName | None = None,
) -> typing.Any | None:
    return dataclasses.field(
        default=default, metadata={"parser": XMLAttr(default, qname)}
    )


@typing.overload
def Child(*, default: None, expr: str | None = ...) -> typing.Any | None: ...
@typing.overload
def Child(*, default: _MISSING_TYPE = ..., expr: str | None = ...) -> typing.Any: ...
def Child(
    *, default: None | _MISSING_TYPE = MISSING, expr: str | None = None
) -> typing.Any | None:
    return dataclasses.field(
        default=default, metadata={"parser": XMLChild(default=default, expr=expr)}
    )


def ChildList() -> list[typing.Any]:
    return dataclasses.field(metadata={"parser": XMLChildList()})


@typing.overload
def ChildText(*, default: bool, qname: QName | None = ...) -> bool: ...
@typing.overload
def ChildText(*, default: str, qname: QName | None = ...) -> str: ...
@typing.overload
def ChildText(*, default: int, qname: QName | None = ...) -> int: ...
@typing.overload
def ChildText(*, default: float, qname: QName | None = ...) -> float: ...
@typing.overload
def ChildText(*, default: JID, qname: QName | None = ...) -> JID: ...
@typing.overload
def ChildText(*, default: None, qname: QName | None = ...) -> typing.Any | None: ...
@typing.overload
def ChildText(
    *, default: _MISSING_TYPE = ..., qname: QName | None = ...
) -> typing.Any: ...
def ChildText(
    *, default: ValueTypeT | None | _MISSING_TYPE = MISSING, qname: QName | None = None
) -> typing.Any | None:
    return dataclasses.field(
        default=default, metadata={"parser": XMLChildText(default, qname)}
    )


def ChildFlag(
    default: bool | _MISSING_TYPE = MISSING, qname: QName | None = None
) -> bool:
    return dataclasses.field(metadata={"parser": XMLChildFlag(default, qname)})


@typing.overload
def PathValue(*, default: bool, expr: str) -> bool: ...
@typing.overload
def PathValue(*, default: str, expr: str) -> str: ...
@typing.overload
def PathValue(*, default: int, expr: str) -> int: ...
@typing.overload
def PathValue(*, default: float, expr: str) -> float: ...
@typing.overload
def PathValue(*, default: JID, expr: str) -> JID: ...
@typing.overload
def PathValue(*, default: None, expr: str) -> typing.Any | None: ...
@typing.overload
def PathValue(*, default: _MISSING_TYPE = ..., expr: str) -> typing.Any: ...
def PathValue(
    *, default: ValueTypeT | None | _MISSING_TYPE = MISSING, expr: str
) -> typing.Any:
    return dataclasses.field(
        default=default, metadata={"parser": XMLPathValue(default, expr)}
    )


# TODO: are they needed?
def ChildValue(
    child_converter: ChildConverter,
    default: ValueTypeT | None | _MISSING_TYPE = MISSING,
) -> typing.Any:
    return dataclasses.field(
        metadata={"parser": XMLChildValue(child_converter, default)}
    )


def ChildValueList(
    child_converter: ChildConverter, required: bool = False
) -> typing.Any:
    return dataclasses.field(
        metadata={"parser": XMLChildValueList(child_converter, required)}
    )


@typing.dataclass_transform(
    field_specifiers=(
        Attr,
        Child,
        ChildList,
        ChildText,
        ChildValue,
        ChildValueList,
        ChildFlag,
    )
)
def xml_model(f: type[typing.Any]):
    return dataclasses.dataclass(f)
