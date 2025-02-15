# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any
from typing import ParamSpec
from typing import TYPE_CHECKING
from typing import TypeVar

import functools
import inspect
import logging
from collections.abc import Callable
from urllib.parse import unquote
from urllib.parse import urlparse

from nbxmpp.errors import is_error
from nbxmpp.errors import StanzaError
from nbxmpp.protocol import Iq
from nbxmpp.simplexml import Node
from nbxmpp.structs import CommonResult

if TYPE_CHECKING:
    from nbxmpp.dispatcher import NBXMPPModuleT
    from nbxmpp.task import Task

T = TypeVar("T")
P = ParamSpec("P")


def process_response(response: Iq) -> CommonResult:
    if response.isError():
        raise StanzaError(response)

    return CommonResult(jid=response.getFrom())


def raise_if_error(result: Any) -> None:
    if is_error(result):
        raise result


def finalize(task: Task, result: Any) -> Any:
    if is_error(result):
        raise result
    if isinstance(result, Node):
        return task.set_result(result)
    return result


def parse_xmpp_uri(uri: str) -> tuple[str, str, dict[str, str]]:
    url = urlparse(uri)
    if url.scheme != "xmpp":
        raise ValueError("not a xmpp uri")

    if ";" not in url.query:
        return (url.path, url.query, {})

    action, query = url.query.split(";", 1)
    key_value_pairs = query.split(";")

    dict_: dict[str, str] = {}
    for key_value in key_value_pairs:
        key, value = key_value.split("=")
        dict_[key] = unquote(value)

    return (url.path, action, dict_)


def make_func_arguments_string(
    func: Callable[..., Any], self: Any, args: Any, kwargs: Any
) -> str:
    signature = inspect.signature(func)
    bound_arguments = signature.bind(self, *args, **kwargs)
    bound_arguments.apply_defaults()
    arg_string = ""
    for name, arg in bound_arguments.arguments.items():
        if name == "self":
            continue
        arg_string += f"{name}={arg}, "
    arg_string = arg_string[:-2]
    return f"{func.__name__}({arg_string})"


def log_calls(func: Callable[P, T]) -> Callable[P, T]:
    @functools.wraps(func)
    def func_wrapper(self: NBXMPPModuleT, *args: Any, **kwargs: Any) -> T:
        if self._log.isEnabledFor(logging.INFO):  # type: ignore
            self._log.info(make_func_arguments_string(func, self, args, kwargs))  # type: ignore
        return func(self, *args, **kwargs)

    return func_wrapper
