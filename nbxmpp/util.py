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


class PropertyDict:
    def __init__(self):
        self.__data = {}

    def __getattr__(self, key):
        return self.__data[key]

    def __setattr__(self, key, value):
        if '__' in key:
            super().__setattr__(key, value)
        else:
            self.__data[key] = value
