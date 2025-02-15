from test.lib.util import StanzaHandlerTest

from nbxmpp.modules.reactions import Reactions
from nbxmpp.protocol import Message
from nbxmpp.structs import Reactions as ReactionStruct


class MockLog:
    @staticmethod
    def warning(_):
        pass


class MockModule:
    _log = MockLog

    @staticmethod
    def is_emoji(s):
        return Reactions.is_emoji(s)


class ReactionsTest(StanzaHandlerTest):
    def test_reaction_parsing(self):
        class P:
            reactions: ReactionStruct

        xml = """
            <message to='romeo@capulet.net/orchard' id='96d73204-a57a-11e9-88b8-4889e7820c76' type='chat'>
              <reactions id='744f6e18-a57a-11e9-a656-4889e7820c76' xmlns='urn:xmpp:reactions:0'>
                <reaction>👋  </reaction>
                <reaction>🐢</reaction>
              </reactions>
              <store xmlns='urn:xmpp:hints'/>
            </message>
        """
        msg = Message(node=xml)
        Reactions._process_message_reaction(MockModule, self, msg, P)

        self.assertEqual(P.reactions.id, "744f6e18-a57a-11e9-a656-4889e7820c76")
        self.assertEqual(P.reactions.emojis, {"👋", "🐢"})

    def test_no_reactions(self):
        class P:
            reactions: ReactionStruct = None

        xml = """
            <message to='romeo@capulet.net/orchard' id='96d73204-a57a-11e9-88b8-4889e7820c76' type='chat'>
              <store xmlns='urn:xmpp:hints'/>
            </message>
        """
        msg = Message(node=xml)
        Reactions._process_message_reaction(MockModule, self, msg, P)

        self.assertIsNone(P.reactions)

    def test_empty_reactions(self):
        class P:
            reactions: ReactionStruct

        xml = """
            <message to='romeo@capulet.net/orchard' id='96d73204-a57a-11e9-88b8-4889e7820c76' type='chat'>
              <reactions id='744f6e18-a57a-11e9-a656-4889e7820c76' xmlns='urn:xmpp:reactions:0' />
              <store xmlns='urn:xmpp:hints'/>
            </message>
        """
        msg = Message(node=xml)
        Reactions._process_message_reaction(MockModule, self, msg, P)

        self.assertEqual(len(P.reactions.emojis), 0)

    def test_invalid_reactions_no_id(self):
        class P:
            reactions: ReactionStruct

        xml = """
            <message to='romeo@capulet.net/orchard' id='96d73204-a57a-11e9-88b8-4889e7820c76' type='chat'>
              <reactions xmlns='urn:xmpp:reactions:0'>
                <reaction>👋</reaction>
                <reaction>🐢</reaction>
              </reactions>
              <store xmlns='urn:xmpp:hints'/>
            </message>
        """
        msg = Message(node=xml)
        Reactions._process_message_reaction(MockModule, self, msg, P)
        self.assertFalse(hasattr(P, "reactions"))

    def test_invalid_reactions_empty_id(self):
        class P:
            reactions: ReactionStruct

        xml = """
            <message to='romeo@capulet.net/orchard' id='96d73204-a57a-11e9-88b8-4889e7820c76' type='chat'>
              <reactions id='' xmlns='urn:xmpp:reactions:0'>
                <reaction>👋</reaction>
                <reaction>🐢</reaction>
              </reactions>
              <store xmlns='urn:xmpp:hints'/>
            </message>
        """
        msg = Message(node=xml)
        Reactions._process_message_reaction(MockModule, self, msg, P)
        self.assertFalse(hasattr(P, "reactions"))

    def test_invalid_reactions_empty_emoji(self):
        class P:
            reactions: ReactionStruct

        xml = """
            <message to='romeo@capulet.net/orchard' id='96d73204-a57a-11e9-88b8-4889e7820c76' type='chat'>
              <reactions id='sadfsadf' xmlns='urn:xmpp:reactions:0'>
                <reaction></reaction>
                <reaction>🐢</reaction>
              </reactions>
              <store xmlns='urn:xmpp:hints'/>
            </message>
        """
        msg = Message(node=xml)
        Reactions._process_message_reaction(MockModule, self, msg, P)
        self.assertEqual(P.reactions.emojis, {"🐢"})

    def test_set_reactions(self):
        x = Message()
        x.setReactions("id", "🐢")
        self.assertEqual(x.getReactions(), ("id", {"🐢"}))

        x = Message()
        x.setReactions("id", "🐢👋")
        self.assertEqual(x.getReactions(), ("id", {"🐢", "👋"}))

        x = Message()
        x.setReactions("id", "")
        self.assertEqual(x.getReactions(), ("id", set()))

        x = Message()
        self.assertIsNone(x.getReactions())
