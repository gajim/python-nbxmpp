## rndg.py
##
##   cryptographically secure pseudo-random number generator.
##   When possible use OpenSSL PRNG combined with os.random,
##   if OpenSSL PRNG is not available, use only os.random.
##
## Copyright (C) 2013 Fedor Brunner <fedor.brunner@azet.sk>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

USE_PYOPENSSL = False
try:
    import OpenSSL.rand
    import binascii, os
    USE_PYOPENSSL = True
except ImportError:
    import random

if not USE_PYOPENSSL:
    getrandbits = random.SystemRandom().getrandbits
else:
    def getrandbits(k):
        """getrandbits(k) -> x.  Generates a long int with k random bits."""
        if k <= 0:
            raise ValueError('number of bits must be greater than zero')
        if k != int(k):
            raise TypeError('number of bits should be an integer')

        bytes = (k + 7) // 8                    # bits / 8 and rounded up

        # Add system entropy to OpenSSL PRNG
        OpenSSL.rand.add(os.urandom(bytes), bytes)
        # Extract random bytes from OpenSSL PRNG
        random_str = OpenSSL.rand.bytes(bytes)

        x = long(binascii.hexlify(random_str), 16)
        return x >> (bytes * 8 - k)             # trim excess bits
