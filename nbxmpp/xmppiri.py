
import re
from gi.repository import GLib


# https://www.rfc-editor.org/rfc/rfc3987

ucschar        = r'\xA0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF'\
    r'\U00010000-\U0001FFFD\U00020000-\U0002FFFD\U00030000-\U0003FFFD'\
    r'\U00040000-\U0004FFFD\U00050000-\U0005FFFD\U00060000-\U0006FFFD'\
    r'\U00070000-\U0007FFFD\U00080000-\U0008FFFD\U00090000-\U0009FFFD'\
    r'\U000A0000-\U000AFFFD\U000B0000-\U000BFFFD\U000C0000-\U000CFFFD'\
    r'\U000D0000-\U000DFFFD\U000E1000-\U000EFFFD'
unreserved     = r'A-Za-z0-9\-._~'
iunreserved    = fr'{unreserved}{ucschar}'
subdelims = r"!$&'()*+,;="

# https://www.rfc-editor.org/rfc/rfc5122.html#section-2.2
nodeallow  = r"!$()*+,;="
resallow   = r"!$&'()*+,:;="

# ifragment without iunreserved and pct-encoded
reserved_chars_allowed_in_ifragment = subdelims + ":@" + "/?"

rx_ikey        = f'[{iunreserved}]*'
rx_iquerytype  = f'[{iunreserved}]*'


def validate_ikey(ikey: str) -> str:
    res = re.fullmatch(rx_ikey, ikey)
    if res is None:
        raise ValueError('Not allowed characters in key')
    return ikey


def validate_querytype(querytype: str) -> str:
    res = re.fullmatch(rx_iquerytype, querytype)
    if res is None:
        raise ValueError('Not allowed characters in querytype')
    return querytype


def escape_ifragment(ifragment: str) -> str:
    return GLib.Uri.escape_string(
        ifragment, reserved_chars_allowed_in_ifragment, True)


def escape_ivalue(ivalue: str) -> str:
    return GLib.Uri.escape_string(ivalue, None, True)


def escape_inode(inode: str) -> str:
    return GLib.Uri.escape_string(inode, nodeallow, True)


def escape_ires(ires: str) -> str:
    return GLib.Uri.escape_string(ires, resallow, True)
