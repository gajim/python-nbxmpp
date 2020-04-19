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

import logging
import hashlib

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import BobData
from nbxmpp.util import b64decode

log = logging.getLogger('nbxmpp.m.bob')


def parse_bob_data(stanza):
    data_node = stanza.getTag('data', namespace=Namespace.BOB)
    if data_node is None:
        return None

    cid = data_node.getAttr('cid')
    type_ = data_node.getAttr('type')
    max_age = data_node.getAttr('max-age')
    if max_age is not None:
        try:
            max_age = int(max_age)
        except Exception:
            log.exception(stanza)
            return None

    if cid is None or type_ is None:
        log.warning('Invalid data node (no cid or type attr): %s', stanza)
        return None

    try:
        algo_hash = cid.split('@')[0]
        algo, hash_ = algo_hash.split('+')
    except Exception:
        log.exception('Invalid cid: %s', stanza)
        return None

    bob_data = data_node.getData()
    if not bob_data:
        log.warning('No bob data found: %s', stanza)
        return None

    try:
        bob_data = b64decode(bob_data, return_type=bytes)
    except Exception:
        log.warning('Unable to decode data')
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
        log.warning('Invalid hash: %s', stanza)
        return None

    return BobData(algo=algo,
                   hash_=hash_,
                   max_age=max_age,
                   data=bob_data,
                   cid=cid,
                   type=type_)
