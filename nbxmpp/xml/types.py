# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

from abc import ABC
from abc import abstractmethod


class AbstractXMLDataType(ABC):
    @staticmethod
    @abstractmethod
    def deserialize(value: str) -> Any:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def serialize(value: Any) -> str:
        raise NotImplementedError


class Integer(AbstractXMLDataType):
    @staticmethod
    def deserialize(value: str) -> int:
        return int(value)

    @staticmethod
    def serialize(value: int) -> str:
        return str(value)


class Float(AbstractXMLDataType):
    @staticmethod
    def deserialize(value: str) -> float:
        return float(value)

    @staticmethod
    def serialize(value: float) -> str:
        return str(value)


class String(AbstractXMLDataType):
    @staticmethod
    def deserialize(value: str) -> str:
        return value

    @staticmethod
    def serialize(value: str) -> str:
        return value


class Bool(AbstractXMLDataType):
    @staticmethod
    def deserialize(value: str) -> bool:
        if value in ("1", "true"):
            return True

        if value in ("0", "false"):
            return False

        raise ValueError(f"Invalid boolean attribute {value!r}")

    @staticmethod
    def serialize(value: bool) -> str:
        return "true" if value else "false"
