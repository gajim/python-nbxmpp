from __future__ import annotations

from typing import Any

import logging
import operator
from dataclasses import dataclass

from nbxmpp.exceptions import FallbackLanguageError
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message


@dataclass(frozen=True)
class FallbackRange:
    start: int
    end: int


FallbackLangMapT = dict[str | None, FallbackRange | None]
FallbacksForT = dict[str, FallbackLangMapT | None]


def parse_fallback_indication(
    log: logging.Logger | logging.LoggerAdapter[Any], stanza: Message
) -> FallbacksForT | None:
    fallbacks = stanza.getTags(
        "fallback",
        namespace=Namespace.FALLBACK,
    )
    if not fallbacks:
        return None

    fallbacks_for: FallbacksForT = {}
    for fallback in fallbacks:
        for_ = fallback.getAttr("for")
        if not for_:
            log.warning('Missing "for" attribute on fallback indication')
            continue

        bodies = fallback.getTags("body")
        if not bodies:
            fallbacks_for[for_] = None
            continue

        fallback_lang_map: FallbackLangMapT = {}
        for body in bodies:
            lang = body.getAttr("xml:lang") or None
            start = body.getAttr("start") or None
            end = body.getAttr("end") or None

            if type(start) is not type(end):
                log.warning("Incorrect range on fallback indication")
                continue

            range_ = None
            if start is not None:
                assert end is not None
                try:
                    range_ = FallbackRange(start=int(start), end=int(end))
                except Exception:
                    log.warning("Incorrect range on fallback indication")
                    continue

            fallback_lang_map[lang] = range_

        if fallback_lang_map:
            # Only store data for the key if there was at least one
            # valid body
            fallbacks_for[for_] = fallback_lang_map

    return fallbacks_for


def strip_fallback(
    fallbacks_for: FallbacksForT,
    fallback_ns: set[str],
    lang: str | None,
    text: str,
) -> str:
    fallbacks: list[FallbackRange] = []
    # Gather all fallbacks we support
    for ns in fallback_ns:
        try:
            fallback_lang_map = fallbacks_for[ns]
        except KeyError:
            continue

        if fallback_lang_map is None:
            # At least one of the fallbacks declared the whole
            # body as fallback
            return ""

        try:
            range_ = fallback_lang_map[lang]
        except KeyError:
            # Fallback missing for this language, assume the stanza is
            # malformed and return the whole text
            raise FallbackLanguageError

        if range_ is None:
            # No range means the whole body is considered a fallback
            return ""

        fallbacks.append(range_)

    if not fallbacks:
        return text

    fallbacks.sort(key=operator.attrgetter("start"), reverse=True)

    stripped_text = text
    for range_ in fallbacks:
        stripped_text = stripped_text[: range_.start] + stripped_text[range_.end :]

    return stripped_text
