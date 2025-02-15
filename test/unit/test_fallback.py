from __future__ import annotations

from test.lib.util import StanzaHandlerTest
from unittest.mock import MagicMock

import nbxmpp
from nbxmpp.exceptions import FallbackLanguageError
from nbxmpp.language import LanguageRange
from nbxmpp.modules.fallback import FallbackRange
from nbxmpp.modules.fallback import FallbacksForT
from nbxmpp.modules.fallback import parse_fallback_indication
from nbxmpp.modules.fallback import strip_fallback
from nbxmpp.structs import BodyData


class TestFallback(StanzaHandlerTest):

    def test_parse_fallback_indication(self):
        xml = """
            <message to='anna@example.com' id='message-id2' type='groupchat'>
              <body>> Anna wrote:\n> Hi, how are you?\nGreat</body>
              <fallback xmlns='urn:xmpp:fallback:0' for='urn:xmpp:test:0'>
                <body start='0' end='33' />
                <body xml:lang='en' start='0' end='32' />
                <body xml:lang='de' start='0' end='31' />
              </fallback>
              <fallback xmlns='urn:xmpp:fallback:0' for='urn:xmpp:test:1'>
                <body />
              </fallback>
              <fallback xmlns='urn:xmpp:fallback:0' for='urn:xmpp:test:2' />
            </message>
        """

        log = MagicMock()
        message = nbxmpp.Message(node=xml)

        fallbacks_for = parse_fallback_indication(log, message)

        expected = {
            "urn:xmpp:test:0": {
                None: FallbackRange(0, 33),
                "en": FallbackRange(0, 32),
                "de": FallbackRange(0, 31),
            },
            "urn:xmpp:test:1": {
                None: None,
            },
            "urn:xmpp:test:2": None,
        }

        self.assertEqual(fallbacks_for, expected)

    def test_strip_fallback(self):
        fallbacks_for: FallbacksForT = {
            "urn:xmpp:test:1": {
                None: FallbackRange(33, 38),
            },
            "urn:xmpp:test:0": {
                None: FallbackRange(0, 14),
                "en": FallbackRange(0, 33),
            },
            "urn:xmpp:test:2": {
                None: FallbackRange(54, 55),
                "en": None,
            },
        }

        text = "> Anna wrote:\n> Hi, how are you?\nGreat"

        # Strip one fallback with unavailable language
        with self.assertRaises(FallbackLanguageError):
            stripped_text = strip_fallback(
                fallbacks_for, {"urn:xmpp:test:0"}, "xx", text
            )

        # Strip one fallback with language
        stripped_text = strip_fallback(fallbacks_for, {"urn:xmpp:test:0"}, "en", text)
        self.assertEqual(stripped_text, "Great")

        # Strip one fallback with no language
        stripped_text = strip_fallback(fallbacks_for, {"urn:xmpp:test:0"}, None, text)
        self.assertEqual(stripped_text, "> Hi, how are you?\nGreat")

        # Strip multiple fallbacks in correct order
        stripped_text = strip_fallback(
            fallbacks_for, {"urn:xmpp:test:0", "urn:xmpp:test:1"}, None, text
        )
        self.assertEqual(stripped_text, "> Hi, how are you?\n")

        # Range out of bounds, don’t strip anything
        stripped_text = strip_fallback(fallbacks_for, {"urn:xmpp:test:2"}, None, text)
        self.assertEqual(stripped_text, text)

        # One Range is None, so whole body is fallback
        stripped_text = strip_fallback(
            fallbacks_for, {"urn:xmpp:test:0", "urn:xmpp:test:2"}, "en", text
        )
        self.assertEqual(stripped_text, "")

    def test_body_with_fallback(self):
        text = "> Anna wrote:\n> Hi, how are you?\nGreat"
        text_de = "> Anna schrieb\n>Hallo, wie geht es dir?\nGut"

        xml = """
            <message to='anna@example.com' id='message-id2' type='groupchat'>
              <body>%s</body>
              <body xml:lang='en'>%s</body>
              <body xml:lang='de'>%s</body>
              <fallback xmlns='urn:xmpp:fallback:0' for='urn:xmpp:test:0'>
                <body start='0' end='33' />
                <body xml:lang='en' start='0' end='33' />
                <body xml:lang='de' start='0' end='40' />
              </fallback>
              <fallback xmlns='urn:xmpp:fallback:0' for='urn:xmpp:test:1'>
                <body />
              </fallback>
              <fallback xmlns='urn:xmpp:fallback:0' for='urn:xmpp:test:2' />
            </message>
        """ % (
            text,
            text,
            text_de,
        )

        log = MagicMock()
        message = nbxmpp.Message(node=xml)

        fallbacks_for = parse_fallback_indication(log, message)

        body_data = BodyData(message, fallbacks_for, {"urn:xmpp:test:0"})
        body = body_data.get([LanguageRange(tag="en")])
        self.assertEqual(body, "Great")

        body = body_data.get(None)
        self.assertEqual(body, "Great")

        body = body_data.get([LanguageRange(tag="de")])
        self.assertEqual(body, "Gut")

        body_data = BodyData(message, fallbacks_for, {"urn:xmpp:test:1"})
        # specific language body requested
        # but there is no fallback for this language
        body = body_data.get([LanguageRange(tag="en")])
        self.assertEqual(body, text)

        body = body_data.get(None)
        self.assertEqual(body, "")

        body_data = BodyData(message, fallbacks_for, {"urn:xmpp:test:2"})
        # specific language body requested
        # fallback is for all bodies
        body = body_data.get([LanguageRange(tag="en")])
        self.assertEqual(body, "")

        body = body_data.get(None)
        self.assertEqual(body, "")
