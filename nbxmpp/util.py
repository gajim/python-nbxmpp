# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

import base64
from collections import namedtuple

StanzaHandler = namedtuple('StanzaHandler', 'name callback typ ns xmlns system priority')
StanzaHandler.__new__.__defaults__ = ('', '', None, False, 50)


def b64decode(data, return_type=str):
    if isinstance(data, str):
        data = data.encode()
    result = base64.b64decode(data)
    if return_type == bytes:
        return result
    return result.decode()


def b64encode(data, return_type=str):
    if isinstance(data, str):
        data = data.encode()
    result = base64.b64encode(data)
    if return_type == bytes:
        return result
    return result.decode()


class PropertyBase:
    def __init__(self):
        self._data = {}

    def __getattr__(self, key):
        return self._data[key]

    def __setattr__(self, key, value):
        if '_data' in key:
            super().__setattr__(key, value)
        else:
            self._data[key] = value


class MessagePropertyDict(PropertyBase):
    def __init__(self):
        self._data = {
            'carbon_type': None,
            'eme': None,
            'http_auth': None,
        }

    @property
    def is_http_auth(self):
        return self._data['http_auth'] is not None


class IqPropertyDict(PropertyBase):
    def __init__(self):
        self._data = {
            'http_auth': None,
        }

    @property
    def is_http_auth(self):
        return self._data['http_auth'] is not None


def get_property_dict(name):
    if name == 'message':
        return MessagePropertyDict()
    if name == 'iq':
        return IqPropertyDict()
    return PropertyBase()
