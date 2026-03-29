from __future__ import annotations

from typing import Any

import dataclasses
import functools
import os
import sqlite3

import idna
from gi.repository import GLib

from . import exceptions
from . import precis
from . import stringprep
from . import xmppiri

_localpart_escape_chars = " \"&'/:<>@"


def split_jid_string(jid_string: str) -> tuple[str | None, str, str | None]:
    # https://tools.ietf.org/html/rfc7622#section-3.2

    # Remove any portion from the first '/' character to the end of the
    # string (if there is a '/' character present).

    # Remove any portion from the beginning of the string to the first
    # '@' character (if there is an '@' character present).

    if jid_string.find("/") != -1:
        rest, resourcepart = jid_string.split("/", 1)
    else:
        rest, resourcepart = jid_string, None

    if rest.find("@") != -1:
        localpart, domainpart = rest.split("@", 1)
    else:
        localpart, domainpart = None, rest

    return localpart, domainpart, resourcepart


@functools.cache
def validate_localpart(localpart: str) -> str:
    if not localpart or len(localpart.encode()) > 1023:
        raise exceptions.LocalpartByteLimit

    if os.environ.get("NBXMPP_ENFORCE_PRECIS") is None:
        try:
            return stringprep.nodeprep(localpart)
        except Exception:
            try:
                return precis.enforce_precis_username(localpart)
            except Exception:
                raise exceptions.LocalpartNotAllowedChar

    try:
        return precis.enforce_precis_username(localpart)
    except Exception:
        raise exceptions.LocalpartNotAllowedChar


@functools.cache
def validate_resourcepart(resourcepart: str) -> str:
    if not resourcepart or len(resourcepart.encode()) > 1023:
        raise exceptions.ResourcepartByteLimit

    if os.environ.get("NBXMPP_ENFORCE_PRECIS") is None:
        try:
            return stringprep.resourceprep(resourcepart)
        except Exception:
            try:
                return precis.enforce_precis_opaque(resourcepart)
            except Exception:
                raise exceptions.ResourcepartNotAllowedChar

    try:
        return precis.enforce_precis_opaque(resourcepart)
    except Exception:
        raise exceptions.ResourcepartNotAllowedChar


@functools.cache
def validate_domainpart(domainpart: str) -> str:
    if not domainpart:
        raise exceptions.DomainpartByteLimit

    ip_address = domainpart.strip("[]")
    if GLib.hostname_is_ip_address(ip_address):
        return ip_address

    length = len(domainpart.encode())
    if length == 0 or length > 1023:
        raise exceptions.DomainpartByteLimit

    if domainpart.endswith("."):  # RFC7622, 3.2
        domainpart = domainpart[:-1]

    try:
        domainpart = idna2008_prep(domainpart)
    except Exception:
        raise exceptions.DomainpartNotAllowedChar

    return domainpart


@functools.cache
def idna2008_prep(domain: str, to_ascii: bool = False) -> str:
    """
    Prepare with UTS46 case mapping to stay compatibel with the IDNA2003
    mapping. Further try to encode the domain to catch illegal domains.
    Only return the case mapped domain because on the XMPP wire,UTF8 domains
    are fine.
    """
    domain = idna.uts46_remap(domain)
    encoded_domain = idna.encode(domain)
    if to_ascii:
        return encoded_domain.decode()
    return domain


@functools.cache
def escape_localpart(localpart: str) -> str:
    # https://xmpp.org/extensions/xep-0106.html#bizrules-algorithm
    #
    # If there are any instances of character sequences that correspond
    # to escapings of the disallowed characters
    # (e.g., the character sequence "\27") or the escaping character
    # (i.e., the character sequence "\5c") in the source address,
    # the leading backslash character MUST be escaped to the character
    # sequence "\5c"

    for char in "\\" + _localpart_escape_chars:
        seq = "\\{:02x}".format(ord(char))
        localpart = localpart.replace(seq, "\\5c{:02x}".format(ord(char)))

    # Escape all other chars
    for char in _localpart_escape_chars:
        localpart = localpart.replace(char, "\\{:02x}".format(ord(char)))

    return localpart


@functools.cache
def unescape_localpart(localpart: str) -> str:
    if localpart.startswith("\\20") or localpart.endswith("\\20"):
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


@dataclasses.dataclass(frozen=True, kw_only=True)
class JID:
    localpart: str | None
    domain: str
    resource: str | None

    def __init__(
        self,
        localpart: str | None,
        domain: str,
        resource: str | None,
    ):
        if localpart is not None:
            localpart = validate_localpart(localpart)
        object.__setattr__(self, "localpart", localpart)

        domain = validate_domainpart(domain)
        object.__setattr__(self, "domain", domain)

        if resource is not None:
            resource = validate_resourcepart(resource)
        object.__setattr__(self, "resource", resource)

    @classmethod
    @functools.cache
    def from_string(cls, jid_string: str, force_bare: bool = False) -> JID:
        localpart, domainpart, resourcepart = split_jid_string(jid_string)

        if force_bare:
            resourcepart = None

        try:
            return cls(localpart=localpart, domain=domainpart, resource=resourcepart)
        except Exception as error:
            raise exceptions.InvalidJid('Unable to parse "%s"' % jid_string) from error

    @classmethod
    @functools.cache
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

        if "@" in user_input:
            localpart, domainpart = user_input.rsplit("@", 1)
            if localpart.startswith(" ") or localpart.endswith(" "):
                raise exceptions.LocalpartNotAllowedChar

            localpart = escape_localpart(localpart)

        else:
            localpart = None
            domainpart = user_input

        try:
            return cls(localpart=localpart, domain=domainpart, resource=None)
        except Exception as error:
            raise exceptions.InvalidJid('Unable to parse "%s"' % user_input) from error

    @classmethod
    @functools.cache
    def from_iri(cls, iri_str: str, *, force_bare: bool = False) -> JID:
        try:
            iri_str = xmppiri.clean_iri(iri_str)
        except ValueError as error:
            raise exceptions.InvalidJid('Unable to parse "%s"' % iri_str) from error

        localpart, domainpart, resourcepart = split_jid_string(iri_str)

        if localpart is not None:
            localpart = GLib.Uri.unescape_string(localpart)

        if force_bare:
            resourcepart = None

        if resourcepart is not None:
            resourcepart = GLib.Uri.unescape_string(resourcepart)

        try:
            return cls(localpart=localpart, domain=domainpart, resource=resourcepart)
        except Exception as error:
            raise exceptions.InvalidJid('Unable to parse "%s"' % iri_str) from error

    def __str__(self) -> str:
        if self.localpart:
            jid = f"{self.localpart}@{self.domain}"
        else:
            jid = self.domain

        if self.resource is not None:
            return f"{jid}/{self.resource}"
        return jid

    def __conform__(self, protocol: sqlite3.PrepareProtocol | Any) -> str:
        if protocol is sqlite3.PrepareProtocol:
            return str(self)
        raise ValueError

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            try:
                return JID.from_string(other) == self
            except Exception:
                return False

        if isinstance(other, JID):
            return (
                self.localpart == other.localpart
                and self.domain == other.domain
                and self.resource == other.resource
            )

        return False

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def domain_to_ascii(self) -> str:
        return idna2008_prep(self.domain, to_ascii=True)

    @property
    def bare(self) -> str:
        if self.localpart is not None:
            return f"{self.localpart}@{self.domain}"
        return self.domain

    @property
    def is_bare(self) -> bool:
        return self.resource is None

    def new_as_bare(self) -> JID:
        if self.resource is None:
            return self
        return JID.from_string(self.bare)

    def bare_match(self, other: str | JID) -> bool:
        if isinstance(other, str):
            other = JID.from_string(other)
        return self.bare == other.bare

    @property
    def is_domain(self) -> bool:
        return self.localpart is None and self.resource is None

    @property
    def is_full(self) -> bool:
        return self.localpart is not None and self.resource is not None

    def new_with(self, **kwargs: Any) -> JID:
        new = dataclasses.asdict(self)
        new.update(kwargs)
        return JID(**new)

    def to_user_string(self, show_punycode: bool = True) -> str:
        domain = self.domain_to_ascii()
        if domain.startswith("xn--") and show_punycode:
            domain_encoded = f" ({domain})"
        else:
            domain_encoded = ""

        if self.localpart is None:
            return f"{self}{domain_encoded}"

        localpart = unescape_localpart(self.localpart)

        if self.resource is None:
            return f"{localpart}@{self.domain}{domain_encoded}"
        return f"{localpart}@{self.domain}/{self.resource}{domain_encoded}"

    def to_iri(
        self,
        query: str | tuple[str, list[tuple[str, str]]] | None = None,
        fragment: str | None = None,
    ) -> str:
        if self.localpart:
            inode = xmppiri.escape_inode(self.localpart)
            ipathxmpp = f"{inode}@{self.domain}"
        else:
            ipathxmpp = f"{self.domain}"

        if self.resource is not None:
            ires = xmppiri.escape_ires(self.resource)
            ipathxmpp = f"{ipathxmpp}/{ires}"

        iri = f"xmpp:{ipathxmpp}"

        if query is not None:
            if isinstance(query, str):
                querytype = query
                queryparams = None
            else:
                querytype, queryparams = query

            iquerytype = xmppiri.validate_querytype(querytype)
            iri += f"?{iquerytype}"

            if queryparams is not None:
                for ikey, ivalue in queryparams:
                    ivalue = xmppiri.escape_ivalue(ivalue)
                    ikey = xmppiri.validate_ikey(ikey)
                    iri += f";{ikey}={ivalue}"

        if fragment is not None:
            ifragment = xmppiri.escape_ifragment(fragment)
            iri += f"#{ifragment}"

        return iri
