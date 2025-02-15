import datetime
from test.lib.util import StanzaHandlerTest

from nbxmpp import Message
from nbxmpp.modules.muc.moderation import Moderation
from nbxmpp.protocol import JID
from nbxmpp.structs import MessageProperties


class TestModeration(StanzaHandlerTest):
    def test_parse_moderation_message(self):
        xml = """
        <message type="groupchat" id='retraction-id-1' from='room@muc.example.com' to="room@muc.example.com/macbeth">
          <retract id="stanza-id-1" xmlns='urn:xmpp:message-retract:1'>
            <moderated by='room@muc.example.com/macbeth' xmlns='urn:xmpp:message-moderate:1'>
              <occupant-id xmlns="urn:xmpp:occupant-id:0" id="dd72603deec90a38ba552f7c68cbcc61bca202cd" />
            </moderated>
            <reason>Some Reason</reason>
          </retract>
        </message>
        """

        props = MessageProperties("mockjid")
        message = Message(node=xml)
        Moderation._process_moderation_1_message(None, None, message, props)

        assert props.moderation is not None
        self.assertEqual(props.moderation.stanza_id, "stanza-id-1")
        self.assertEqual(
            props.moderation.by, JID.from_string("room@muc.example.com/macbeth")
        )
        self.assertEqual(props.moderation.reason, "Some Reason")
        self.assertIsInstance(props.moderation.stamp, datetime.datetime)
        self.assertFalse(props.moderation.is_tombstone)
        self.assertEqual(
            props.moderation.occupant_id, "dd72603deec90a38ba552f7c68cbcc61bca202cd"
        )
