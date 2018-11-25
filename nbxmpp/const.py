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

from enum import Enum
from enum import unique

@unique
class Realm(Enum):
    CONNECTING = 'Connecting'

    def __str__(self):
        return self.value


@unique
class Event(Enum):
    AUTH_SUCCESSFUL = 'Auth successful'
    AUTH_FAILED = 'Auth failed'
    BIND_FAILED = 'Bind failed'
    SESSION_FAILED = 'Session failed'
    RESUME_SUCCESSFUL = 'Resume successful'
    RESUME_FAILED = 'Resume failed'
    CONNECTION_ACTIVE = 'Connection active'

    def __str__(self):
        return self.value
