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
from typing import Union

import logging
import functools
import inspect
from urllib.parse import urlparse
from urllib.parse import unquote

from nbxmpp import types
from nbxmpp.structs import CommonResult
from nbxmpp.errors import BaseError, StanzaError
from nbxmpp.errors import is_error


def process_response(response: types.Iq) -> CommonResult:
    if response.is_error():
        raise StanzaError(response)

    return CommonResult(jid=response.get_from())


def raise_if_error(result: Union[BaseError, types.Iq]) -> None:
    if is_error(result):
        raise result


def finalize(result: Any) -> Any:
    if is_error(result):
        raise result

    return result


def parse_xmpp_uri(uri: str) -> tuple[str, str, dict[str, str]]:
    url = urlparse(uri)
    if url.scheme != 'xmpp':
        raise ValueError('not a xmpp uri')

    if not ';' in url.query:
        return (url.path, url.query, {})

    action, query = url.query.split(';', 1)
    key_value_pairs = query.split(';')

    dict_: dict[str, str] = {}
    for key_value in key_value_pairs:
        key, value = key_value.split('=')
        dict_[key] = unquote(value)

    return (url.path, action, dict_)


def make_func_arguments_string(func, self, args, kwargs):
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


def log_calls(func):
    @functools.wraps(func)
    def func_wrapper(self, *args, **kwargs):
        if self._log.isEnabledFor(logging.INFO):
            self._log.info(make_func_arguments_string(func, self, args, kwargs))
        return func(self, *args, **kwargs)
    return func_wrapper
