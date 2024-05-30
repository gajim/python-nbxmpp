# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

# Initial version taken from https://github.com/horazont/aioxmpp
# Modified on 30-AUG-2022

from __future__ import annotations

import stringprep
from collections.abc import Callable
from unicodedata import ucd_3_2_0

_nodeprep_prohibited = frozenset("\"&'/:<>@")


def is_RandALCat(c: str) -> bool:
    return ucd_3_2_0.bidirectional(c) in ("R", "AL")


def is_LCat(c: str) -> bool:
    return ucd_3_2_0.bidirectional(c) == "L"


def check_nodeprep_prohibited(char: str) -> bool:
    return char in _nodeprep_prohibited


def _check_against_tables(
    chars: list[str], tables: tuple[Callable[[str], bool], ...]
) -> str | None:
    """
    Perform a check against the table predicates in `tables`. `tables` must be
    a reusable iterable containing characteristic functions of character sets,
    that is, functions which return :data:`True` if the character is in the
    table.
    The function returns the first character occuring in any of the tables or
    :data:`None` if no character matches.
    """

    for c in chars:
        if any(in_table(c) for in_table in tables):
            return c

    return None


def do_normalization(chars: list[str]) -> None:
    """
    Perform the stringprep normalization. Operates in-place on a list of
    unicode characters provided in `chars`.
    """
    chars[:] = list(ucd_3_2_0.normalize("NFKC", "".join(chars)))


def check_bidi(chars: list[str]) -> None:
    """
    Check proper bidirectionality as per stringprep. Operates on a list of
    unicode characters provided in `chars`.
    """

    # the empty string is valid, as it cannot violate the RandALCat constraints
    if not chars:
        return

    # first_is_RorAL = ucd_3_2_0.bidirectional(chars[0]) in {"R", "AL"}
    # if first_is_RorAL:

    has_RandALCat = any(is_RandALCat(c) for c in chars)
    if not has_RandALCat:
        return

    has_LCat = any(is_LCat(c) for c in chars)
    if has_LCat:
        raise ValueError("L and R/AL characters must not occur in the same" " string")

    if not is_RandALCat(chars[0]) or not is_RandALCat(chars[-1]):
        raise ValueError("R/AL string must start and end with R/AL character.")


def check_against_tables(
    chars: list[str], bad_tables: tuple[Callable[[str], bool], ...]
) -> None:
    """
    Check against tables, by checking whether any of the characters
    from `chars` are in any of the `bad_tables`.
    Operates in-place on a list of code points from `chars`.
    """
    violator = _check_against_tables(chars, bad_tables)
    if violator is not None:
        raise ValueError(
            "Input contains prohibited or unassigned codepoint: "
            "U+{:04x}".format(ord(violator))
        )


def _nodeprep_do_mapping(chars: list[str]) -> None:
    i = 0
    while i < len(chars):
        c = chars[i]
        if stringprep.in_table_b1(c):
            del chars[i]
        else:
            replacement = stringprep.map_table_b2(c)
            if replacement != c:
                chars[i : (i + 1)] = list(replacement)
            i += len(replacement)


def nodeprep(string: str, allow_unassigned: bool = False) -> str:
    """
    Process the given `string` using the Nodeprep (`RFC 6122`_) profile. In the
    error cases defined in `RFC 3454`_ (stringprep), a :class:`ValueError` is
    raised.
    """

    chars = list(string)
    _nodeprep_do_mapping(chars)
    do_normalization(chars)
    check_against_tables(
        chars,
        (
            stringprep.in_table_c11,
            stringprep.in_table_c12,
            stringprep.in_table_c21,
            stringprep.in_table_c22,
            stringprep.in_table_c3,
            stringprep.in_table_c4,
            stringprep.in_table_c5,
            stringprep.in_table_c6,
            stringprep.in_table_c7,
            stringprep.in_table_c8,
            stringprep.in_table_c9,
            check_nodeprep_prohibited,
        ),
    )
    check_bidi(chars)

    if not allow_unassigned:
        check_against_tables(chars, (stringprep.in_table_a1,))

    return "".join(chars)


def _resourceprep_do_mapping(chars: list[str]) -> None:
    i = 0
    while i < len(chars):
        c = chars[i]
        if stringprep.in_table_b1(c):
            del chars[i]
            continue
        i += 1


def resourceprep(string: str, allow_unassigned: bool = False) -> str:
    """
    Process the given `string` using the Resourceprep (`RFC 6122`_) profile. In
    the error cases defined in `RFC 3454`_ (stringprep), a :class:`ValueError`
    is raised.
    """

    chars = list(string)
    _resourceprep_do_mapping(chars)
    do_normalization(chars)
    check_against_tables(
        chars,
        (
            stringprep.in_table_c12,
            stringprep.in_table_c21,
            stringprep.in_table_c22,
            stringprep.in_table_c3,
            stringprep.in_table_c4,
            stringprep.in_table_c5,
            stringprep.in_table_c6,
            stringprep.in_table_c7,
            stringprep.in_table_c8,
            stringprep.in_table_c9,
        ),
    )
    check_bidi(chars)

    if not allow_unassigned:
        check_against_tables(chars, (stringprep.in_table_a1,))

    return "".join(chars)


def nameprep(string: str, allow_unassigned: bool = False) -> str:
    """
    Process the given `string` using the Nameprep (`RFC 3491`_) profile. In the
    error cases defined in `RFC 3454`_ (stringprep), a :class:`ValueError` is
    raised.
    """

    chars = list(string)
    _nodeprep_do_mapping(chars)
    do_normalization(chars)
    check_against_tables(
        chars,
        (
            stringprep.in_table_c12,
            stringprep.in_table_c22,
            stringprep.in_table_c3,
            stringprep.in_table_c4,
            stringprep.in_table_c5,
            stringprep.in_table_c6,
            stringprep.in_table_c7,
            stringprep.in_table_c8,
            stringprep.in_table_c9,
        ),
    )
    check_bidi(chars)

    if not allow_unassigned:
        check_against_tables(chars, (stringprep.in_table_a1,))

    return "".join(chars)


def _saslprep_do_mapping(chars: list[str]) -> None:
    i = 0
    while i < len(chars):
        c = chars[i]
        if stringprep.in_table_b1(c):
            del chars[i]

        elif stringprep.in_table_c12(c):
            chars[i] = " "

        i += 1


def saslprep(string: str, allow_unassigned: bool = False) -> str:
    """
    Process the given `string` using the SASLprep (`RFC 4013`_) profile.
    """

    chars = list(string)
    _saslprep_do_mapping(chars)
    do_normalization(chars)
    check_against_tables(
        chars,
        (
            stringprep.in_table_c12,
            stringprep.in_table_c21,
            stringprep.in_table_c22,
            stringprep.in_table_c3,
            stringprep.in_table_c4,
            stringprep.in_table_c5,
            stringprep.in_table_c6,
            stringprep.in_table_c7,
            stringprep.in_table_c8,
            stringprep.in_table_c9,
        ),
    )
    check_bidi(chars)

    if not allow_unassigned:
        check_against_tables(chars, (stringprep.in_table_a1,))

    return "".join(chars)
