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

from typing import Optional

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import RSMData


def parse_rsm(element: types.Base) -> Optional[RSMData]:
    set_element = element.find_tag('set', namespace=Namespace.RSM)
    if set_element is None:
        return None

    after = set_element.find_tag_text('after') or None
    before = set_element.find_tag_text('before') or None
    last = set_element.find_tag_text('last') or None

    first = None
    first_index = None

    first_element = set_element.find_tag('first')
    if first_element is not None:
        first = first.text
        try:
            first_index = int(first_element.get('index'))
        except Exception:
            pass

    try:
        count = int(set_element.find_tag_text('count'))
    except Exception:
        count = None

    try:
        max_ = int(set_element.find_tag_text('max'))
    except Exception:
        max_ = None

    try:
        index = int(set_element.find_tag_text('index'))
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
