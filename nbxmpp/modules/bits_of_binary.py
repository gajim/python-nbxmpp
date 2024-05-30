# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import hashlib
import logging

from nbxmpp.namespaces import Namespace
from nbxmpp.simplexml import Node
from nbxmpp.structs import BobData
from nbxmpp.util import b64decode

log = logging.getLogger("nbxmpp.m.bob")


def parse_bob_data(stanza: Node) -> BobData | None:
    data_node = stanza.getTag("data", namespace=Namespace.BOB)
    if data_node is None:
        return None

    cid = data_node.getAttr("cid")
    type_ = data_node.getAttr("type")
    max_age = data_node.getAttr("max-age")
    if max_age is not None:
        try:
            max_age = int(max_age)
        except Exception:
            log.exception(stanza)
            return None

    assert max_age is not None

    if cid is None or type_ is None:
        log.warning("Invalid data node (no cid or type attr): %s", stanza)
        return None

    try:
        algo_hash = cid.split("@")[0]
        algo, hash_ = algo_hash.split("+")
    except Exception:
        log.exception("Invalid cid: %s", stanza)
        return None

    bob_data = data_node.getData()
    if not bob_data:
        log.warning("No bob data found: %s", stanza)
        return None

    try:
        bob_data = b64decode(bob_data)
    except Exception:
        log.warning("Unable to decode data")
        log.exception(stanza)
        return None

    try:
        sha = hashlib.new(algo)
    except ValueError as error:
        log.warning(stanza)
        log.warning(error)
        return None

    sha.update(bob_data)
    if sha.hexdigest() != hash_:
        log.warning("Invalid hash: %s", stanza)
        return None

    return BobData(
        algo=algo, hash_=hash_, max_age=max_age, data=bob_data, cid=cid, type=type_
    )
