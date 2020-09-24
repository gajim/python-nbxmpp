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

from urllib.parse import urlparse
from urllib.parse import unquote

from nbxmpp.structs import CommonResult
from nbxmpp.errors import StanzaError
from nbxmpp.errors import is_error
from nbxmpp.simplexml import Node


def process_response(response):
    if response.isError():
        raise StanzaError(response)

    return CommonResult(jid=response.getFrom())


def raise_if_error(result):
    if is_error(result):
        raise result


def finalize(task, result):
    if is_error(result):
        raise result
    if isinstance(result, Node):
        return task.set_result(result)
    return result


def parse_xmpp_uri(uri):
    url = urlparse(uri)
    if url.scheme != 'xmpp':
        raise ValueError('not a xmpp uri')

    if not ';' in url.query:
        return (url.path, url.query, {})

    action, query = url.query.split(';', 1)
    key_value_pairs = query.split(';')

    dict_ = {}
    for key_value in key_value_pairs:
        key, value = key_value.split('=')
        dict_[key] = unquote(value)

    return (url.path, action, dict_)
