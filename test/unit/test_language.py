from __future__ import annotations

from typing import Any

import collections.abc
import unittest

from nbxmpp.language import basic_filter_languages
from nbxmpp.language import LanguageMap
from nbxmpp.language import LanguageRange
from nbxmpp.language import LanguageTag
from nbxmpp.language import lookup_language


class TestLanguageTag(unittest.TestCase):
    def test_init(self):
        with self.assertRaises(TypeError):
            LanguageTag("foo")

        with self.assertRaises(ValueError):
            LanguageTag(tag="")

        with self.assertRaises(TypeError):
            LanguageTag()

    def test_fromstr_match_str(self):
        tag = LanguageTag.fromstr("de-Latn-DE-1999")
        self.assertEqual("de-latn-de-1999", tag.match_str)

    def test_fromstr_print_str(self):
        tag = LanguageTag.fromstr("de-Latn-DE-1999")
        self.assertEqual("de-Latn-DE-1999", tag.print_str)

    def test___str__(self):
        tag = LanguageTag.fromstr("zh-Hans")
        self.assertEqual("zh-Hans", str(tag))
        tag = LanguageTag.fromstr("de-Latn-DE-1999")
        self.assertEqual("de-Latn-DE-1999", str(tag))

    def test_compare_case_insensitively(self):
        tag1 = LanguageTag.fromstr("de-DE")
        tag2 = LanguageTag.fromstr("de-de")
        tag3 = LanguageTag.fromstr("fr")

        self.assertTrue(tag1 == tag2)
        self.assertFalse(tag1 != tag2)
        self.assertTrue(tag2 == tag1)
        self.assertFalse(tag2 != tag1)

        self.assertTrue(tag1 != tag3)
        self.assertFalse(tag1 == tag3)
        self.assertTrue(tag2 != tag3)
        self.assertFalse(tag2 == tag3)

        self.assertTrue(tag3 != tag1)
        self.assertFalse(tag3 == tag1)
        self.assertTrue(tag3 != tag1)
        self.assertFalse(tag3 == tag1)

    def test_order_case_insensitively(self):
        tag1 = LanguageTag.fromstr("de-DE")
        tag2 = LanguageTag.fromstr("de-de")
        tag3 = LanguageTag.fromstr("en-us")
        tag4 = LanguageTag.fromstr("fr")

        self.assertLess(tag1, tag3)
        self.assertLess(tag1, tag4)
        self.assertLess(tag2, tag3)
        self.assertLess(tag2, tag4)
        self.assertLess(tag3, tag4)

        self.assertGreater(tag4, tag3)
        self.assertGreater(tag4, tag2)
        self.assertGreater(tag4, tag1)
        self.assertGreater(tag3, tag2)
        self.assertGreater(tag3, tag1)

        self.assertFalse(tag1 > tag2)
        self.assertFalse(tag2 > tag1)

        self.assertFalse(tag1 < tag2)
        self.assertFalse(tag2 < tag1)

    def test_hash_case_insensitively(self):
        tag1 = LanguageTag.fromstr("de-DE")
        tag2 = LanguageTag.fromstr("de-de")

        self.assertEqual(hash(tag1), hash(tag2))

    def test_not_equal_to_None(self):
        tag1 = LanguageTag.fromstr("de-DE")
        self.assertNotEqual(tag1, None)

    def test_dont_compare_with_None(self):
        tag1 = LanguageTag.fromstr("de-DE")
        with self.assertRaises(TypeError):
            tag1 > None  # noqa: B015
        with self.assertRaises(TypeError):
            tag1 < None  # noqa: B015
        with self.assertRaises(TypeError):
            tag1 >= None  # noqa: B015
        with self.assertRaises(TypeError):
            tag1 <= None  # noqa: B015

    def test__repr__(self):
        tag1 = LanguageTag.fromstr("de-DE")
        tag2 = LanguageTag.fromstr("fr")

        self.assertEqual("<nbxmpp.language.LanguageTag.fromstr('de-DE')>", repr(tag1))

        self.assertEqual("<nbxmpp.language.LanguageTag.fromstr('fr')>", repr(tag2))

    def test_immutable(self):
        tag = LanguageTag.fromstr("foo")
        with self.assertRaises(AttributeError):
            tag.foo = "bar"


class TestLanguageRange(unittest.TestCase):
    def test_init(self):
        with self.assertRaises(TypeError):
            LanguageRange("foo")

        with self.assertRaises(ValueError):
            LanguageRange(tag="")

        with self.assertRaises(TypeError):
            LanguageRange()

    def test_fromstr_match_str(self):
        tag = LanguageRange.fromstr("de-DE")
        self.assertEqual("de-de", tag.match_str)

    def test_fromstr_print_str(self):
        tag = LanguageRange.fromstr("de-Latn-DE-1999")
        self.assertEqual("de-Latn-DE-1999", tag.print_str)

    def test___str__(self):
        tag = LanguageRange.fromstr("zh-Hans")
        self.assertEqual("zh-Hans", str(tag))
        tag = LanguageRange.fromstr("de-Latn-DE-1999")
        self.assertEqual("de-Latn-DE-1999", str(tag))

    def test_compare_case_insensitively(self):
        tag1 = LanguageRange.fromstr("de-DE")
        tag2 = LanguageRange.fromstr("de-de")
        tag3 = LanguageRange.fromstr("fr")

        self.assertTrue(tag1 == tag2)
        self.assertFalse(tag1 != tag2)
        self.assertTrue(tag2 == tag1)
        self.assertFalse(tag2 != tag1)

        self.assertTrue(tag1 != tag3)
        self.assertFalse(tag1 == tag3)
        self.assertTrue(tag2 != tag3)
        self.assertFalse(tag2 == tag3)

        self.assertTrue(tag3 != tag1)
        self.assertFalse(tag3 == tag1)
        self.assertTrue(tag3 != tag1)
        self.assertFalse(tag3 == tag1)

    def test_hash_case_insensitively(self):
        tag1 = LanguageRange.fromstr("de-DE")
        tag2 = LanguageRange.fromstr("de-de")

        self.assertEqual(hash(tag1), hash(tag2))

    def test_not_equal_to_None(self):
        r1 = LanguageRange.fromstr("de-DE")
        self.assertNotEqual(r1, None)

    def test_wildcard(self):
        r1 = LanguageRange.fromstr("*")
        r2 = LanguageRange.fromstr("*")
        self.assertIs(r1, r2)

    def test_strip_rightmost(self):
        r = LanguageRange.fromstr("de-Latn-DE-x-foo")
        self.assertEqual(LanguageRange.fromstr("de-Latn-DE"), r.strip_rightmost())
        self.assertEqual(
            LanguageRange.fromstr("de-Latn"), r.strip_rightmost().strip_rightmost()
        )
        self.assertEqual(
            LanguageRange.fromstr("de"),
            r.strip_rightmost().strip_rightmost().strip_rightmost(),
        )
        with self.assertRaises(ValueError):
            r.strip_rightmost().strip_rightmost().strip_rightmost().strip_rightmost()

    def test_immutable(self):
        r = LanguageRange.fromstr("foo")
        with self.assertRaises(AttributeError):
            r.foo = "bar"


class TestBasicFilterLanguages(unittest.TestCase):
    def setUp(self):
        self.languages = [
            LanguageTag.fromstr("de-Latn-DE-1999"),
            LanguageTag.fromstr("de-DE"),
            LanguageTag.fromstr("de-Latn"),
            LanguageTag.fromstr("fr-CH"),
            LanguageTag.fromstr("it"),
        ]

    def test_filter(self):
        self.assertSequenceEqual(
            [
                self.languages[0],
                self.languages[1],
                self.languages[2],
            ],
            list(
                basic_filter_languages(
                    self.languages,
                    list(
                        map(
                            LanguageRange.fromstr,
                            [
                                "de",
                            ],
                        )
                    ),
                )
            ),
        )

        self.assertSequenceEqual(
            [
                self.languages[1],
            ],
            list(
                basic_filter_languages(
                    self.languages,
                    list(
                        map(
                            LanguageRange.fromstr,
                            [
                                "de-DE",
                            ],
                        )
                    ),
                )
            ),
        )

        self.assertSequenceEqual(
            [
                self.languages[0],
                self.languages[2],
            ],
            list(
                basic_filter_languages(
                    self.languages,
                    list(
                        map(
                            LanguageRange.fromstr,
                            [
                                "de-Latn",
                            ],
                        )
                    ),
                )
            ),
        )

    def test_filter_no_dupes_and_ordered(self):
        self.assertSequenceEqual(
            [
                self.languages[0],
                self.languages[2],
                self.languages[1],
            ],
            list(
                basic_filter_languages(
                    self.languages,
                    list(
                        map(
                            LanguageRange.fromstr,
                            [
                                "de-Latn",
                                "de",
                            ],
                        )
                    ),
                )
            ),
        )

    def test_filter_wildcard(self):
        self.assertSequenceEqual(
            self.languages,
            list(
                basic_filter_languages(
                    self.languages,
                    list(
                        map(
                            LanguageRange.fromstr,
                            [
                                "fr",
                                "*",
                            ],
                        )
                    ),
                )
            ),
        )


class TestLookupLanguage(unittest.TestCase):
    def setUp(self):
        self.languages = [
            LanguageTag.fromstr("de-Latn-DE-1999"),
            LanguageTag.fromstr("fr-CH"),
            LanguageTag.fromstr("it"),
        ]

    def test_match_direct(self):
        self.assertEqual(
            LanguageTag.fromstr("fr-CH"),
            lookup_language(
                self.languages,
                list(map(LanguageRange.fromstr, ["en", "fr-ch", "de-de"])),
            ),
        )

        self.assertEqual(
            LanguageTag.fromstr("it"),
            lookup_language(
                self.languages,
                list(
                    map(
                        LanguageRange.fromstr,
                        [
                            "it",
                        ],
                    )
                ),
            ),
        )

    def test_decay(self):
        self.assertEqual(
            LanguageTag.fromstr("de-Latn-DE-1999"),
            lookup_language(
                self.languages,
                list(map(LanguageRange.fromstr, ["de-de", "en-GB", "en"])),
            ),
        )

        self.assertEqual(
            LanguageTag.fromstr("fr-CH"),
            lookup_language(
                self.languages,
                list(
                    map(
                        LanguageRange.fromstr,
                        [
                            "fr-FR",
                            "de-DE",
                            "fr",
                        ],
                    )
                ),
            ),
        )

    def test_decay_skips_extension_prefixes_properly(self):
        self.assertEqual(
            LanguageTag.fromstr("de-DE"),
            lookup_language(
                list(
                    map(
                        LanguageTag.fromstr,
                        [
                            "de-DE",
                            "de-x",
                        ],
                    )
                ),
                list(
                    map(
                        LanguageRange.fromstr,
                        [
                            "de-x-foobar",
                        ],
                    )
                ),
            ),
        )


class TestLanguageMap(unittest.TestCase):
    def test_implements_mapping(self):
        mapping = LanguageMap()
        self.assertIsInstance(mapping, collections.abc.MutableMapping)

    def test_mapping_interface(self):
        key1 = LanguageTag.fromstr("de-DE")
        key2 = LanguageTag.fromstr("en-US")
        key3 = LanguageTag.fromstr("en")

        mapping = LanguageMap()

        self.assertFalse(mapping)
        self.assertEqual(0, len(mapping))

        mapping[key1] = 10

        self.assertIn(key1, mapping)
        self.assertEqual(10, mapping[key1])

        self.assertSetEqual({key1}, set(mapping))

        mapping[key2] = 20

        self.assertIn(key2, mapping)
        self.assertEqual(20, mapping[key2])

        self.assertSetEqual({key1, key2}, set(mapping))

        key2_prime = LanguageTag.fromstr("en-us")

        self.assertIn(key2_prime, mapping)
        self.assertEqual(20, mapping[key2_prime])

        self.assertNotIn(key3, mapping)

        del mapping[key1]

        self.assertNotIn(key1, mapping)

        mapping.clear()

        self.assertNotIn(key2, mapping)

    def test_lookup(self):
        key1 = LanguageTag.fromstr("de-DE")
        key2 = LanguageTag.fromstr("en-US")
        key3 = LanguageTag.fromstr("en")

        mapping = LanguageMap()

        mapping[key1] = 10
        mapping[key2] = 20
        mapping[key3] = 30

        self.assertEqual(30, mapping.lookup([LanguageRange.fromstr("en-GB")]))

    def test_values(self):
        key1 = LanguageTag.fromstr("de-DE")
        key2 = LanguageTag.fromstr("en-US")
        key3 = LanguageTag.fromstr("en")

        mapping = LanguageMap()

        mapping[key1] = 10
        mapping[key2] = 20
        mapping[key3] = 30

        self.assertSetEqual({10, 20, 30}, set(mapping.values()))

    def test_keys(self):
        key1 = LanguageTag.fromstr("de-DE")
        key2 = LanguageTag.fromstr("en-US")
        key3 = LanguageTag.fromstr("en")

        mapping = LanguageMap()

        mapping[key1] = 10
        mapping[key2] = 20
        mapping[key3] = 30

        self.assertSetEqual({key1, key2, key3}, set(mapping.keys()))

    def test_items(self):
        key1 = LanguageTag.fromstr("de-DE")
        key2 = LanguageTag.fromstr("en-US")
        key3 = LanguageTag.fromstr("en")

        mapping = LanguageMap()

        mapping[key1] = 10
        mapping[key2] = 20
        mapping[key3] = 30

        self.assertSetEqual(
            {
                (key1, 10),
                (key2, 20),
                (key3, 30),
            },
            set(mapping.items()),
        )

    def test_equality(self):
        mapping1 = LanguageMap()
        mapping1[LanguageTag.fromstr("de-de")] = 10
        mapping1[LanguageTag.fromstr("en-US")] = 20

        mapping2 = LanguageMap()
        mapping2[LanguageTag.fromstr("de-DE")] = 10
        mapping2[LanguageTag.fromstr("en-US")] = 20

        mapping3 = LanguageMap()
        mapping3[LanguageTag.fromstr("de-DE")] = 10
        mapping3[LanguageTag.fromstr("en-GB")] = 20

        self.assertEqual(mapping1, mapping2)
        self.assertFalse(mapping1 != mapping2)

        self.assertNotEqual(mapping1, mapping3)
        self.assertFalse(mapping1 == mapping3)

        self.assertNotEqual(mapping2, mapping3)
        self.assertFalse(mapping2 == mapping3)

    def test_setdefault(self):
        l: list[Any] = []
        mapping = LanguageMap()
        result = mapping.setdefault(LanguageTag.fromstr("de-de"), l)

        self.assertIs(result, l)

        result = mapping.setdefault(LanguageTag.fromstr("de-de"), [])

        self.assertIs(result, l)

    def test_lookup_returns_None_key_if_nothing_matches(self):
        mapping = LanguageMap()
        mapping[None] = "foobar"
        mapping[LanguageTag.fromstr("de")] = "Test"
        mapping[LanguageTag.fromstr("en")] = "test"

        self.assertEqual("foobar", mapping.lookup([LanguageRange.fromstr("it")]))

    def test_any_returns_only_key(self):
        m = LanguageMap()
        m[None] = "fnord"

        self.assertEqual(m.any(), "fnord")

        m = LanguageMap()
        m[LanguageTag.fromstr("de")] = "Test"

        self.assertEqual(m.any(), "Test")

    def test_any_raises_ValueError_on_empty_map(self):
        m = LanguageMap()
        with self.assertRaises(ValueError):
            m.any()

    def test_any_prefers_None(self):
        m = LanguageMap()
        m[LanguageTag.fromstr("de")] = "Test"
        m[None] = "fnord"

        self.assertEqual(m.any(), "fnord")

        m = LanguageMap()
        m[None] = "fnord"
        m[LanguageTag.fromstr("de")] = "Test"

        self.assertEqual(m.any(), "fnord")

    def test_any_returns_same_key_for_same_keyset(self):
        m = LanguageMap()
        m[LanguageTag.fromstr("de")] = "Test"
        m[LanguageTag.fromstr("fr")] = "fnord"

        self.assertEqual(m.any(), "Test")

        m = LanguageMap()
        m[LanguageTag.fromstr("fr")] = "fnord"
        m[LanguageTag.fromstr("de")] = "Test"

        self.assertEqual(m.any(), "Test")
