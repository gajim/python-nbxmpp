from __future__ import annotations

import functools
import re
from collections.abc import Callable

# https://www.rfc-editor.org/rfc/rfc3987
ucschar = (
    "\xa0-\ud7ff"
    "\uf900-\ufdcf"
    "\ufdf0-\uffef"
    "\U00010000-\U0001fffd"
    "\U00020000-\U0002fffd"
    "\U00030000-\U0003fffd"
    "\U00040000-\U0004fffd"
    "\U00050000-\U0005fffd"
    "\U00060000-\U0006fffd"
    "\U00070000-\U0007fffd"
    "\U00080000-\U0008fffd"
    "\U00090000-\U0009fffd"
    "\U000a0000-\U000afffd"
    "\U000b0000-\U000bfffd"
    "\U000c0000-\U000cfffd"
    "\U000d0000-\U000dfffd"
    "\U000e1000-\U000efffd"
)

ALPHA = "A-Za-z"
DIGIT = "0-9"
unreserved = rf"{ALPHA}{DIGIT}\-\._\~"
subdelims = "!$&'()*+,;="
iunreserved = f"{unreserved}{ucschar}"
ipchar = f"{iunreserved}{re.escape(subdelims)}:@"
ifragment = rf"{ipchar}/\?"

# https://www.rfc-editor.org/rfc/rfc5122.html#section-2.2
nodeallow = r"!$()*+,;="
resallow = r"!$&'()*+,:;="
inode = f"{iunreserved}{re.escape(nodeallow)}"
ires = f"{iunreserved}{re.escape(resallow)}"
ivalue = f"{iunreserved}"

rx_iunreserved = re.compile(f"[{iunreserved}]*")
rx_inode = re.compile(f"[{inode}]")
rx_ires = re.compile(f"[{ires}]")
rx_ikey = rx_iunreserved
rx_iquerytype = rx_iunreserved
rx_ivalue = rx_iunreserved
rx_ifragment = re.compile(f"[{ifragment}]")


class _Quoter(dict[str, str]):
    """A mapping from a string to its percent encoded form.

    Mapping is only done if string is not in safe range.

    Keeps a cache internally, via __missing__, for efficiency (lookups
    of cached keys don't call Python code at all).
    """

    def __init__(self, safe: re.Pattern[str]) -> None:
        self._safe = safe

    def __repr__(self) -> str:
        return f"<Quoter {dict(self)!r}>"

    def __missing__(self, b: str) -> str:
        if len(b) != 1:
            raise ValueError("String must be exactly one character long")

        if self._safe.fullmatch(b) is None:
            res = "".join(["%{:02X}".format(i) for i in b.encode()])
        else:
            res = b
        self[b] = res
        return res


@functools.lru_cache
def _quoter_factory(safe: re.Pattern[str]) -> Callable[[str], str]:
    return _Quoter(safe).__getitem__


def validate_ikey(ikey: str) -> str:
    res = rx_ikey.fullmatch(ikey)
    if res is None:
        raise ValueError("Not allowed characters in key")
    return ikey


def validate_querytype(querytype: str) -> str:
    res = rx_iquerytype.fullmatch(querytype)
    if res is None:
        raise ValueError("Not allowed characters in querytype")
    return querytype


def _escape(string: str, pattern: re.Pattern[str]) -> str:
    quoter = _quoter_factory(safe=pattern)
    return "".join([quoter(c) for c in string])


def escape_ifragment(fragment: str) -> str:
    return _escape(fragment, rx_ifragment)


def escape_ivalue(value: str) -> str:
    return _escape(value, rx_ivalue)


def escape_inode(node: str) -> str:
    return _escape(node, rx_inode)


def escape_ires(res: str) -> str:
    return _escape(res, rx_ires)


def clean_iri(iri_str: str) -> str:
    if not iri_str.startswith("xmpp:"):
        raise ValueError("IRI must start with xmpp scheme")

    iri_str = iri_str.removeprefix("xmpp:")

    if iri_str.startswith("//"):
        raise ValueError("IRI with auth component is unsupported")

    # Remove query and fragment
    iri_str = iri_str.split("?", maxsplit=1)[0]
    iri_str = iri_str.split("#", maxsplit=1)[0]
    return iri_str
