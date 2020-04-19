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

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import RSMData


def parse_rsm(stanza):
    stanza = stanza.getTag('set', namespace=Namespace.RSM)
    if stanza is None:
        return None

    after = stanza.getTagData('after') or None
    before = stanza.getTagData('before') or None
    last = stanza.getTagData('last') or None

    first_index = None
    first = stanza.getTagData('first') or None
    if first is not None:
        try:
            first_index = int(first.getAttr('index'))
        except Exception:
            pass

    try:
        count = int(stanza.getTagData('count'))
    except Exception:
        count = None

    try:
        max_ = int(stanza.getTagData('max'))
    except Exception:
        max_ = None

    try:
        index = int(stanza.getTagData('index'))
    except Exception:
        index = None

    return RSMData(after=after,
                   before=before,
                   last=last,
                   first=first,
                   first_index=first_index,
                   count=count,
                   max=max_,
                   index=index)
