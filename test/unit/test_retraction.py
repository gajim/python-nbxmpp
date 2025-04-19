from test.lib.util import StanzaHandlerTest
from test.lib.util import utc_now

from nbxmpp import Message
from nbxmpp import Namespace
from nbxmpp.modules.retraction import Retraction
from nbxmpp.protocol import JID
from nbxmpp.structs import MAMData
from nbxmpp.structs import MessageProperties


class TestRetraction(StanzaHandlerTest):
    def test_parse_retract_direct_message(self):
        # language=XML
        xml = """
        <message type='chat' to='lord@capulet.example' id='retract-message-1'>
          <retract id="origin-id-1" xmlns='urn:xmpp:message-retract:1'/>
          <fallback xmlns="urn:xmpp:fallback:0"/>
          <body>This person attempted to retract a previous message</body>
          <store xmlns="urn:xmpp:hints"/>
        </message>
        """

        timestamp = utc_now()
        props = MessageProperties(
            JID.from_string("mockjid@jid.com"), timestamp=timestamp.timestamp()
        )
        message = Message(node=xml)
        Retraction._process_message_retraction(None, None, message, props)
        assert props.retraction is not None
        self.assertEqual(props.retraction.id, "origin-id-1")
        self.assertFalse(props.retraction.is_tombstone)
        self.assertEqual(props.retraction.timestamp, timestamp)

    def test_parse_retract_groupchat_message(self):
        # language=XML
        xml = """
        <message type='groupchat'
                 to='me@capulet.example/gajim'
                 from='room@component/retracter'>
          <retract id="stanza-id-1" xmlns='urn:xmpp:message-retract:1'/>
          <occupant-id xmlns="urn:xmpp:occupant-id:0" id="occupant-id" />
          <fallback xmlns="urn:xmpp:fallback:0"/>
          <body>This person attempted to retract a previous message</body>
          <store xmlns="urn:xmpp:hints"/>
        </message>
        """

        timestamp = utc_now()
        props = MessageProperties(
            JID.from_string("mockjid@jid.com"), timestamp=timestamp.timestamp()
        )
        message = Message(node=xml)
        Retraction._process_message_retraction(None, None, message, props)
        assert props.retraction is not None
        self.assertEqual(props.retraction.id, "stanza-id-1")
        self.assertFalse(props.retraction.is_tombstone)
        self.assertEqual(props.retraction.timestamp, timestamp)

    def test_parse_retract_tombstone_message(self):
        # language=XML
        xml = """
        <message type='groupchat'
                 to='me@capulet.example/gajim'
                 from='room@component/retracter'>
          <retracted id="ref-to-retract-message-id" xmlns='urn:xmpp:message-retract:1'/>
        </message>
        """

        timestamp = utc_now()
        mam = MAMData(
            id="1",
            query_id="query1",
            archive=JID.from_string("archive@jid.com"),
            namespace="mam:1",
            timestamp=timestamp.timestamp(),
        )
        props = MessageProperties(JID.from_string("mockjid@jid.com"), mam=mam)
        message = Message(node=xml)
        Retraction._process_message_retraction(None, None, message, props)
        assert props.retraction is not None
        self.assertEqual(props.retraction.id, "ref-to-retract-message-id")
        self.assertTrue(props.retraction.is_tombstone)
        self.assertEqual(props.retraction.timestamp, timestamp)

    def test_set_retraction(self):
        msg = Message()
        msg.setRetracted("some-complex-xmpp-message-id")
        self.assertEqual(
            msg.getTagAttr("retract", "id", Namespace.MESSAGE_RETRACT_1),
            "some-complex-xmpp-message-id",
        )
