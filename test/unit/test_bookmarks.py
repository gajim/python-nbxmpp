from test.lib.util import StanzaHandlerTest

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import BookmarkData
from nbxmpp.structs import PubSubEventData
from nbxmpp.structs import StanzaHandler


class BookmarkTest(StanzaHandlerTest):

    def test_bookmark_1_parsing(self):
        def _on_message(_con, _stanza, properties):

            data = [
                BookmarkData(
                    jid=JID.from_string("theplay@conference.shakespeare.lit"),
                    name="The Play's the Thing",
                    autojoin=True,
                    password="pass",  # noqa: S106
                    nick="JC",
                ),
                BookmarkData(
                    jid=JID.from_string("second@conference.shakespeare.lit"),
                    name="Second room",
                    autojoin=False,
                    password=None,
                    nick=None,
                ),
            ]

            pubsub_event = PubSubEventData(
                node="storage:bookmarks",
                id="current",
                item=None,
                data=data,
                deleted=False,
                retracted=False,
                purged=False,
            )

            # We cant compare Node objects
            pubsub_event_ = properties.pubsub_event._replace(item=None)
            self.assertEqual(pubsub_event, pubsub_event_)

        event = """
            <message from='test@test.test'>
                <event xmlns='http://jabber.org/protocol/pubsub#event'>
                    <items node='storage:bookmarks'>
                        <item id='current'>
                            <storage xmlns='storage:bookmarks'>
                                <conference name='The Play&apos;s the Thing'
                                            autojoin='true'
                                            jid='theplay@conference.shakespeare.lit'>
                                    <password>pass</password>
                                    <nick>JC</nick>
                                </conference>
                                <conference name='Second room'
                                            autojoin='0'
                                            jid='second@conference.shakespeare.lit'>
                                </conference>
                            </storage>
                        </item>
                    </items>
                </event>
            </message>
        """

        self.dispatcher.register_handler(
            StanzaHandler(
                name="message", callback=_on_message, ns=Namespace.PUBSUB_EVENT
            )
        )

        self.dispatcher.process_data(event)

    def test_bookmark_2_parsing(self):
        def _on_message(_con, _stanza, properties):

            data = BookmarkData(
                jid=JID.from_string("theplay@conference.shakespeare.lit"),
                name="The Play's the Thing",
                autojoin=True,
                password=None,
                nick="JC",
            )

            pubsub_event = PubSubEventData(
                node="urn:xmpp:bookmarks:0",
                id="theplay@conference.shakespeare.lit",
                item=None,
                data=data,
                deleted=False,
                retracted=False,
                purged=False,
            )

            # We cant compare Node objects
            pubsub_event_ = properties.pubsub_event._replace(item=None)
            self.assertEqual(pubsub_event, pubsub_event_)

        event = """
            <message from='test@test.test'>
                <event xmlns='http://jabber.org/protocol/pubsub#event'>
                    <items node='urn:xmpp:bookmarks:0'>
                        <item id='theplay@conference.shakespeare.lit'>
                            <conference xmlns='urn:xmpp:bookmarks:0'
                                        name='The Play&apos;s the Thing'
                                        autojoin='1'>
                                <nick>JC</nick>
                            </conference>
                        </item>
                    </items>
                </event>
            </message>
        """

        self.dispatcher.register_handler(
            StanzaHandler(
                name="message", callback=_on_message, ns=Namespace.PUBSUB_EVENT
            )
        )

        self.dispatcher.process_data(event)
