# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
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

from typing import TYPE_CHECKING
from typing import Any

import logging

from nbxmpp.util import LogAdapter

if TYPE_CHECKING:
    from nbxmpp.client import Client


class BaseModule:

    _depends: dict[str, str] = {}

    def __init__(self, client: Client):
        logger_name = 'nbxmpp.m.%s' % self.__class__.__name__.lower()
        self._log = LogAdapter(logging.getLogger(logger_name),
                               {'context': client.log_context})

    def __getattr__(self, name: str) -> Any:
        if name not in self._depends:
            raise AttributeError('Unknown method: %s' % name)

        module = self._client.get_module(self._depends[name])
        return getattr(module, name)
