##   protocol.py
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
##
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU General Public License as published by
##   the Free Software Foundation; either version 2, or (at your option)
##   any later version.
##
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU General Public License for more details.

"""
Protocol module contains tools that are needed for processing of xmpp-related
data structures, including jabber-objects like JID or different stanzas and
sub- stanzas) handling routines
"""

from __future__ import annotations

import hashlib
from base64 import b64encode

from gi.repository import GLib

from nbxmpp.namespaces import Namespace



def isMucPM(message):
    muc_user = message.find_tag('x', namespace=Namespace.MUC_USER)
    return (message.get('type') in ('chat', 'error') and
            muc_user is not None and
            not muc_user.get_children())





class Hashes:
    """
    Hash elements for various XEPs as defined in XEP-300

    RECOMENDED HASH USE:
    Algorithm     Support
    MD2           MUST NOT
    MD4           MUST NOT
    MD5           MAY
    SHA-1         MUST
    SHA-256       MUST
    SHA-512       SHOULD
    """

    supported = ('md5', 'sha-1', 'sha-256', 'sha-512')

    def __init__(self, nsp=Namespace.HASHES):
        Node.__init__(self, None, {}, [], None, None, False, None)
        self.setNamespace(nsp)
        self.setName('hash')

    def calculateHash(self, algo, file_string):
        """
        Calculate the hash and add it. It is preferable doing it here
        instead of doing it all over the place in Gajim.
        """
        hl = None
        hash_ = None
        # file_string can be a string or a file
        if isinstance(file_string, str):
            if algo == 'sha-1':
                hl = hashlib.sha1()
            elif algo == 'md5':
                hl = hashlib.md5()
            elif algo == 'sha-256':
                hl = hashlib.sha256()
            elif algo == 'sha-512':
                hl = hashlib.sha512()
            if hl:
                hl.update(file_string)
                hash_ = hl.hexdigest()
        else: # if it is a file
            if algo == 'sha-1':
                hl = hashlib.sha1()
            elif algo == 'md5':
                hl = hashlib.md5()
            elif algo == 'sha-256':
                hl = hashlib.sha256()
            elif algo == 'sha-512':
                hl = hashlib.sha512()
            if hl:
                for line in file_string:
                    hl.update(line)
                hash_ = hl.hexdigest()
        return hash_

    def addHash(self, hash_, algo):
        self.set('algo', algo)
        self.setData(hash_)

class Hashes2:
    """
    Hash elements for various XEPs as defined in XEP-300

    RECOMENDED HASH USE:
    Algorithm     Support
    MD2           MUST NOT
    MD4           MUST NOT
    MD5           MUST NOT
    SHA-1         SHOULD NOT
    SHA-256       MUST
    SHA-512       SHOULD
    SHA3-256      MUST
    SHA3-512      SHOULD
    BLAKE2b256    MUST
    BLAKE2b512    SHOULD
    """

    supported = ('sha-256', 'sha-512', 'sha3-256',
                 'sha3-512', 'blake2b-256', 'blake2b-512')

    def __init__(self, nsp=Namespace.HASHES_2):
        Node.__init__(self, None, {}, [], None, None, False, None)
        self.setNamespace(nsp)
        self.setName('hash')

    def calculateHash(self, algo, file_string):
        """
        Calculate the hash and add it. It is preferable doing it here
        instead of doing it all over the place in Gajim.
        """
        hl = None
        hash_ = None
        if algo == 'sha-256':
            hl = hashlib.sha256()
        elif algo == 'sha-512':
            hl = hashlib.sha512()
        elif algo == 'sha3-256':
            hl = hashlib.sha3_256()
        elif algo == 'sha3-512':
            hl = hashlib.sha3_512()
        elif algo == 'blake2b-256':
            hl = hashlib.blake2b(digest_size=32)
        elif algo == 'blake2b-512':
            hl = hashlib.blake2b(digest_size=64)
        # file_string can be a string or a file
        if hl is not None:
            if isinstance(file_string, bytes):
                hl.update(file_string)
            else: # if it is a file
                for line in file_string:
                    hl.update(line)
            hash_ = b64encode(hl.digest()).decode('ascii')
        return hash_

    def addHash(self, hash_, algo):
        self.set('algo', algo)
        self.setData(hash_)
