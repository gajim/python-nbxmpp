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

from typing import Any
from typing import TYPE_CHECKING

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
    from nbxmpp.task import Task


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
    if url.scheme != 'xmpp':
        raise ValueError('not a xmpp uri')

    if ';' not in url.query:
        return (url.path, url.query, {})

    action, query = url.query.split(';', 1)
    key_value_pairs = query.split(';')

    dict_: dict[str, str] = {}
    for key_value in key_value_pairs:
        key, value = key_value.split('=')
        dict_[key] = unquote(value)

    return (url.path, action, dict_)


def make_func_arguments_string(func: Callable[..., Any], self: Any, args: Any, kwargs: Any) -> str:
    signature = inspect.signature(func)
    bound_arguments = signature.bind(self, *args, **kwargs)
    bound_arguments.apply_defaults()
    arg_string = ''
    for name, arg in bound_arguments.arguments.items():
        if name == 'self':
            continue
        arg_string += f'{name}={arg}, '
    arg_string = arg_string[:-2]
    return f'{func.__name__}({arg_string})'


def log_calls(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def func_wrapper(self: Any, *args: Any, **kwargs: Any):
        if self._log.isEnabledFor(logging.INFO):
            self._log.info(make_func_arguments_string(func, self, args, kwargs))
        return func(self, *args, **kwargs)
    return func_wrapper
