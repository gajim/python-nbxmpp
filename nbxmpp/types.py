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

import typing
from typing import Union
from typing import Literal

from lxml import etree

from nbxmpp.modules.iq import Iq as Iq
from nbxmpp.modules.message import Message as Message
from nbxmpp.modules.presence import Presence as Presence
from nbxmpp.elements import Base as Base

if typing.TYPE_CHECKING:

    # from nbxmpp.modules.iq import Iq as Iq
    from nbxmpp.modules.dataforms import DataForm as DataForm
    from nbxmpp.modules.discovery import DiscoInfo as DiscoInfo
    from nbxmpp.elements import Stanza as Stanza
    from nbxmpp.client import Client as Client
    from nbxmpp.task import Task as Task


BlockingReportValues = Union[Literal['spam'], Literal['abuse']]
Attrs = dict[str, str]
ElementT = etree._Element
