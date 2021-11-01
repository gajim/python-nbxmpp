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

from typing import Union
from typing import Optional
from typing import cast

import functools
import warnings
from dataclasses import dataclass
from dataclasses import asdict

import idna
from gi.repository import GLib
from precis_i18n import get_profile

from nbxmpp import exceptions


_localpart_disallowed_chars = set('"&\'/:<>@')
_localpart_escape_chars = ' "&\'/:<>@'


def deprecation_warning(message: str):
    warnings.warn(message, DeprecationWarning)


@functools.lru_cache(maxsize=None)
def validate_localpart(localpart: str) -> str:
    if not localpart or len(localpart.encode()) > 1023:
        raise exceptions.LocalpartByteLimit

    if _localpart_disallowed_chars & set(localpart):
        raise exceptions.LocalpartNotAllowedChar

    try:
        username = get_profile('UsernameCaseMapped')
        return username.enforce(localpart)
    except Exception:
        raise exceptions.LocalpartNotAllowedChar


@functools.lru_cache(maxsize=None)
def validate_resourcepart(resourcepart: str) -> str:
    if not resourcepart or len(resourcepart.encode()) > 1023:
        raise exceptions.ResourcepartByteLimit

    try:
        opaque = get_profile('OpaqueString')
        return opaque.enforce(resourcepart)
    except Exception:
        raise exceptions.ResourcepartNotAllowedChar


@functools.lru_cache(maxsize=None)
def validate_domainpart(domainpart: str) -> str:
    if not domainpart:
        raise exceptions.DomainpartByteLimit

    ip_address = domainpart.strip('[]')
    if GLib.hostname_is_ip_address(ip_address):
        return ip_address

    length = len(domainpart.encode())
    if length == 0 or length > 1023:
        raise exceptions.DomainpartByteLimit

    if domainpart.endswith('.'):  # RFC7622, 3.2
        domainpart = domainpart[:-1]

    try:
        idna_encode(domainpart)
    except Exception:
        raise exceptions.DomainpartNotAllowedChar

    return domainpart


@functools.lru_cache(maxsize=None)
def idna_encode(domain: str) -> str:
    return idna.encode(domain, uts46=True).decode()


@functools.lru_cache(maxsize=None)
def escape_localpart(localpart: str) -> str:
    # https://xmpp.org/extensions/xep-0106.html#bizrules-algorithm
    #
    # If there are any instances of character sequences that correspond
    # to escapings of the disallowed characters
    # (e.g., the character sequence "\27") or the escaping character
    # (i.e., the character sequence "\5c") in the source address,
    # the leading backslash character MUST be escaped to the character
    # sequence "\5c"

    for char in '\\' + _localpart_escape_chars:
        seq = "\\{:02x}".format(ord(char))
        localpart = localpart.replace(seq, "\\5c{:02x}".format(ord(char)))

    # Escape all other chars
    for char in _localpart_escape_chars:
        localpart = localpart.replace(char, "\\{:02x}".format(ord(char)))

    return localpart


@functools.lru_cache(maxsize=None)
def unescape_localpart(localpart: str) -> str:
    if localpart.startswith('\\20') or localpart.endswith('\\20'):
        # Escaped JIDs are not allowed to start or end with \20
        # so this localpart must be already unescaped
        return localpart

    for char in _localpart_escape_chars:
        seq = "\\{:02x}".format(ord(char))
        localpart = localpart.replace(seq, char)

    for char in _localpart_escape_chars + "\\":
        seq = "\\5c{:02x}".format(ord(char))
        localpart = localpart.replace(seq, "\\{:02x}".format(ord(char)))

    return localpart


@dataclass(frozen=True)
class JID:
    localpart: Optional[str] = None
    domain: Optional[str] = None
    resource: Optional[str] = None

    def __init__(self,
                 localpart: Optional[str] = None,
                 domain: Optional[str] = None,
                 resource: Optional[str] = None):

        if localpart is not None:
            localpart = validate_localpart(localpart)
            object.__setattr__(self, "localpart", localpart)

        domain = validate_domainpart(domain)
        object.__setattr__(self, "domain", domain)

        if resource is not None:
            resource = validate_resourcepart(resource)
            object.__setattr__(self, "resource", resource)

    @classmethod
    @functools.lru_cache(maxsize=None)
    def from_string(cls, jid_string: str) -> JID:
        # https://tools.ietf.org/html/rfc7622#section-3.2

        # Remove any portion from the first '/' character to the end of the
        # string (if there is a '/' character present).

        # Remove any portion from the beginning of the string to the first
        # '@' character (if there is an '@' character present).

        if jid_string.find('/') != -1:
            rest, resourcepart = jid_string.split('/', 1)
        else:
            rest, resourcepart = jid_string, None

        if rest.find('@') != -1:
            localpart, domainpart = rest.split('@', 1)
        else:
            localpart, domainpart = None, rest

        return cls(localpart=localpart,
                   domain=domainpart,
                   resource=resourcepart)

    @classmethod
    @functools.lru_cache(maxsize=None)
    def from_user_input(cls, user_input: str, escaped: bool = False) -> JID:
        # Use this if we want JIDs to be escaped according to XEP-0106
        # The standard JID parsing cannot be applied because user_input is
        # not a valid JID.

        # Only user_input which after escaping result in a bare JID can be
        # successfully parsed.

        # The assumpution is user_input is a bare JID so we start with an
        # rsplit on @ because we assume there is no resource, so the char @
        # in the localpart can later be escaped.

        if escaped:
            # for convenience
            return cls.from_string(user_input)

        if '@' in user_input:
            localpart, domainpart = user_input.rsplit('@', 1)
            if localpart.startswith(' ') or localpart.endswith(' '):
                raise exceptions.LocalpartNotAllowedChar

            localpart = escape_localpart(localpart)

        else:
            localpart = None
            domainpart = user_input

        return cls(localpart=localpart,
                   domain=domainpart,
                   resource=None)

    def __str__(self) -> str:
        if self.localpart:
            jid = f'{self.localpart}@{self.domain}'
        else:
            jid = cast(str, self.domain)

        if self.resource is not None:
            return f'{jid}/{self.resource}'
        return jid

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other: Union[str, JID]) -> bool:
        if isinstance(other, str):
            deprecation_warning('comparing string with JID is deprected')
            try:
                return JID.from_string(other) == self
            except Exception:
                return False

        return (self.localpart == other.localpart and
                self.domain == other.domain and
                self.resource == other.resource)

    def __ne__(self, other: Union[str, JID]) -> bool:
        return not self.__eq__(other)

    def domain_to_ascii(self) -> str:
        return idna_encode(self.domain)

    @property
    def bare(self) -> Optional[str]:
        if self.localpart is not None:
            return f'{self.localpart}@{self.domain}'
        return self.domain

    @property
    def is_bare(self) -> bool:
        return self.resource is None

    def new_as_bare(self) -> JID:
        if self.resource is None:
            return self
        new = asdict(self)
        new.pop('resource')
        return JID(**new)

    def bare_match(self, other: Union[str, JID]) -> bool:
        if isinstance(other, str):
            other = JID.from_string(other)
        return self.bare == other.bare

    @property
    def is_domain(self) -> bool:
        return self.localpart is None and self.resource is None

    @property
    def is_full(self) -> bool:
        return (self.localpart is not None and
                self.domain is not None and
                self.resource is not None)

    def new_with(self, **kwargs: dict[str, str]) -> JID:
        new = asdict(self)
        new.update(kwargs)
        return JID(**new)

    def to_user_string(self, show_punycode: bool = True) -> str:
        domain = self.domain_to_ascii()
        if domain.startswith('xn--') and show_punycode:
            domain_encoded = f' ({domain})'
        else:
            domain_encoded = ''

        if self.localpart is None:
            return f'{self}{domain_encoded}'

        localpart = unescape_localpart(self.localpart)

        if self.resource is None:
            return f'{localpart}@{self.domain}{domain_encoded}'
        return f'{localpart}@{self.domain}/{self.resource}{domain_encoded}'

    def copy(self) -> JID:
        deprecation_warning('copy() is not needed, JID is immutable')
        return self
