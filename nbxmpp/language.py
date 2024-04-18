from __future__ import annotations

from typing import Any
from typing import cast

import functools
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence

# Copied from https://codeberg.org/jssfr/aioxmpp/src/branch/devel/aioxmpp/structs.py


@functools.total_ordering
class LanguageTag:
    """
    Implementation of a language tag. This may be a fully RFC5646 compliant
    implementation some day, but for now it is only very simplistic stub.

    There is no input validation of any kind.
    """

    __slots__ = ("_tag",)

    def __init__(self, *, tag: str):
        if not tag:
            raise ValueError("tag cannot be empty")

        self._tag = tag

    @property
    def match_str(self) -> str:
        """
        The string which is used for matching two language tags. This is the
        lower-cased version of `print_str`.
        """
        return self._tag.lower()

    @property
    def print_str(self) -> str:
        """
        The stringified language tag.
        """
        return self._tag

    @classmethod
    def fromstr(cls, s: str) -> LanguageTag:
        """
        Create a language tag from the given string `s`.
        """
        return cls(tag=s)

    def __str__(self) -> str:
        return self.print_str

    def __eq__(self, other: Any) -> bool:
        try:
            return self.match_str == other.match_str
        except AttributeError:
            return False

    def __lt__(self, other: Any) -> bool:
        try:
            return self.match_str < other.match_str
        except AttributeError:
            return NotImplemented

    def __le__(self, other: Any) -> bool:
        try:
            return self.match_str <= other.match_str
        except AttributeError:
            return NotImplemented

    def __hash__(self) -> int:
        return hash(self.match_str)

    def __repr__(self) -> str:
        return "<{}.{}.fromstr({!r})>".format(
            type(self).__module__, type(self).__qualname__, str(self)
        )


class LanguageRange:
    """
    Implementation of a language range. This may be a fully RFC4647 compliant
    implementation some day, but for now it is only very simplistic stub.

    There is no input validation of any kind.

    LanguageRange instances compare and hash case-insensitively.
    """

    __slots__ = ("_tag",)

    WILDCARD: LanguageRange

    def __init__(self, *, tag: str):
        if not tag:
            raise ValueError("range cannot be empty")

        self._tag = tag

    @property
    def match_str(self) -> str:
        """
        The string which is used for matching two language tags. This is the
        lower-cased version of the `print_str`.
        """
        return self._tag.lower()

    @property
    def print_str(self) -> str:
        """
        The stringified language tag.
        """
        return self._tag

    @classmethod
    def fromstr(cls, s: str) -> LanguageRange:
        """
        Create a language tag from the given string `s`.
        """
        if s == "*":
            return cls.WILDCARD
        return cls(tag=s)

    def __str__(self) -> str:
        return self.print_str

    def __eq__(self, other: Any) -> bool:
        try:
            return self.match_str == other.match_str
        except AttributeError:
            return False

    def __hash__(self) -> int:
        return hash(self.match_str)

    def __repr__(self) -> str:
        return "<{}.{}.fromstr({!r})>".format(
            type(self).__module__, type(self).__qualname__, str(self)
        )

    def strip_rightmost(self) -> LanguageRange:
        """
        Strip the rightmost part of the language range. If the new rightmost
        part is a singleton or ``x`` (i.e. starts an extension or private use
        part), it is also stripped.

        Return the newly created `LanguageRange`.
        """

        parts = self.print_str.split("-")
        parts.pop()
        if parts and len(parts[-1]) == 1:
            parts.pop()
        return type(self).fromstr("-".join(parts))


LanguageRange.WILDCARD = LanguageRange(tag="*")


def basic_filter_languages(
    languages: Sequence[LanguageTag], ranges: Iterable[LanguageRange]
) -> Iterator[LanguageTag]:
    """
    Filter languages using the string-based basic filter algorithm described in
    RFC4647.

    `languages` must be a sequence of `LanguageTag` instances which are
    to be filtered.

    `ranges` must be an iterable which represent the basic language ranges to
    filter with, in priority order. The language ranges must be given as
    `LanguageRange` objects.

    Return an iterator of languages which matched any of the `ranges`. The
    sequence produced by the iterator is in match order and duplicate-free. The
    first range to match a language yields the language into the iterator, no
    other range can yield that language afterwards.
    """

    if LanguageRange.WILDCARD in ranges:
        yield from languages
        return

    found: set[LanguageTag] = set()

    for language_range in ranges:
        range_str = language_range.match_str
        for language in languages:
            if language in found:
                continue

            match_str = language.match_str
            if match_str == range_str:
                yield language
                found.add(language)
                continue

            if len(range_str) < len(match_str):
                if (
                    match_str[: len(range_str)] == range_str
                    and match_str[len(range_str)] == "-"
                ):
                    yield language
                    found.add(language)
                    continue


def lookup_language(
    languages: Sequence[LanguageTag], ranges: Iterable[LanguageRange]
) -> LanguageTag | None:
    """
    Look up a single language in the sequence `languages` using the lookup
    mechanism described in RFC4647. If no match is found, `None` is
    returned. Otherwise, the first matching language is returned.

    `languages` must be a sequence of `LanguageTag` objects, while
    `ranges` must be an iterable of `LanguageRange` objects.
    """

    for language_range in ranges:
        while True:
            try:
                return next(iter(basic_filter_languages(languages, [language_range])))
            except StopIteration:
                pass

            try:
                language_range = language_range.strip_rightmost()
            except ValueError:
                break

    return None


class LanguageMap(dict[LanguageTag | None, Any]):
    """
    A `dict` subclass specialized for holding `LanugageTag`
    instances as keys.

    In addition to the interface provided by `dict`, instances of this
    class also have the following methods:
    """

    def lookup(self, language_ranges: Sequence[LanguageRange]) -> Any:
        """
        Perform an RFC4647 language range lookup on the keys in the
        dictionary. `language_ranges` must be a sequence of
        `LanguageRange` instances.

        Return the entry in the dictionary with a key as produced by
        `lookup_language`. If `lookup_language` does not find a match and the
        mapping contains an entry with key `None`, that entry is
        returned, otherwise `KeyError` is raised.
        """
        keys = list(self.keys())
        try:
            keys.remove(None)
        except ValueError:
            pass

        keys = cast(list[LanguageTag], keys)
        keys.sort()
        key = lookup_language(keys, language_ranges)
        return self[key]

    def any(self) -> Any:
        """
        Returns any element from the language map, preferring the `None`
        key if it is available.

        Guarantees to always return the same element for a map with the same
        keys, even if the keys are iterated over in a different order.
        """
        if not self:
            raise ValueError("any() on empty map")

        try:
            return self[None]
        except KeyError:
            return self[min(self)]  # type: ignore
