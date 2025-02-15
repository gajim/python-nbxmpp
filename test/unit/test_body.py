from __future__ import annotations

from test.lib.util import StanzaHandlerTest

import nbxmpp
from nbxmpp.language import LanguageRange
from nbxmpp.structs import BodyData


class TestBody(StanzaHandlerTest):

    def test_body_language(self):
        text = "> Anna wrote:\n> Hi, how are you?\nGreat"
        text_de = "> Anna schrieb\n>Hallo, wie geht es dir?\nGut"

        xml = """
            <message to='anna@example.com' id='message-id2' type='groupchat'>
              <body>%s</body>
              <body xml:lang='en-us'>%s</body>
              <body xml:lang='de-DE'>%s</body>
            </message>
        """ % (
            text,
            text,
            text_de,
        )

        message = nbxmpp.Message(node=xml)

        body_data = BodyData(message, None, None)
        body = body_data.get([LanguageRange(tag="en")])
        self.assertEqual(body, text)

        body = body_data.get(None)
        self.assertEqual(body, text)

        body = body_data.get([LanguageRange(tag="de")])
        self.assertEqual(body, text_de)

        body = body_data.get([LanguageRange(tag="ar")])
        self.assertEqual(body, text)

        xml = """
            <message to='anna@example.com' id='message-id2' type='groupchat'>
              <body xml:lang='en-us'>en</body>
              <body xml:lang='de-DE'>de</body>
            </message>
        """

        message = nbxmpp.Message(node=xml)

        body_data = BodyData(message)
        body = body_data.get([LanguageRange(tag="en")])
        self.assertEqual(body, "en")

        # Language not in body, pick any language
        body_data = BodyData(message)
        body = body_data.get([LanguageRange(tag="ar")])
        self.assertEqual(body, "de")

        # Supply range with priority
        body_data = BodyData(message)
        body = body_data.get([LanguageRange(tag="de"), LanguageRange(tag="en")])
        self.assertEqual(body, "de")

        body_data = BodyData(message)
        body = body_data.get([LanguageRange(tag="ar"), LanguageRange(tag="en")])
        self.assertEqual(body, "en")
