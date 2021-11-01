
from enum import IntFlag
from typing import Any, Callable, Optional, overload


class Bytes:
    def get_data(self) -> bytes: ...

class Error(Exception):
    def matches(self, domain: int, code: IntFlag) -> bool: ...


class Variant:
    def __getitem__(self, key: Any) -> Any: ...

class MainLoop:

    def run(self) -> None: ...
    def quit(self) -> None: ...

@overload
def idle_add(func: Callable[[Any], Optional[bool]], data: Optional[Any] = ...) -> int: ...

@overload
def idle_add(func: Callable[[], Optional[bool]]) -> int: ...


@overload
def timeout_add_seconds(seconds: int, func: Callable[[], Optional[bool]]) -> int: ...

@overload
def timeout_add_seconds(seconds: int, func: Callable[[Any], Optional[bool]], data: Any) -> int: ...


def source_remove(id: int) -> bool: ...


def quark_try_string(string: Optional[str]) -> int: ...


PRIORITY_DEFAULT: int = 0
