# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Node
from nbxmpp.structs import RSMData


def parse_rsm(stanza: Node) -> RSMData | None:
    stanza = stanza.getTag("set", namespace=Namespace.RSM)
    if stanza is None:
        return None

    after = stanza.getTagData("after") or None
    before = stanza.getTagData("before") or None
    last = stanza.getTagData("last") or None

    first_index = None
    first = stanza.getTagData("first") or None
    if first is not None:
        try:
            first_index = int(first.getAttr("index"))
        except Exception:
            pass

    try:
        count = int(stanza.getTagData("count"))
    except Exception:
        count = None

    try:
        max_ = int(stanza.getTagData("max"))
    except Exception:
        max_ = None

    try:
        index = int(stanza.getTagData("index"))
    except Exception:
        index = None

    return RSMData(
        after=after,
        before=before,
        last=last,
        first=first,
        first_index=first_index,
        count=count,
        max=max_,
        index=index,
    )
