from test.lib.util import StanzaHandlerTest

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import ActivityData
from nbxmpp.structs import PubSubEventData
from nbxmpp.structs import StanzaHandler


class ActivityTest(StanzaHandlerTest):

    def test_activity_parsing(self):
        def _on_message(_con, _stanza, properties):

            data = ActivityData(
                activity="relaxing", subactivity="partying", text="My nurse's birthday!"
            )

            pubsub_event = PubSubEventData(
                node="http://jabber.org/protocol/activity",
                id="b5ac48d0-0f9c-11dc-8754-001143d5d5db",
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
                    <items node='http://jabber.org/protocol/activity'>
                        <item id='b5ac48d0-0f9c-11dc-8754-001143d5d5db'>
                            <activity xmlns='http://jabber.org/protocol/activity'>
                                <relaxing>
                                    <partying/>
                                </relaxing>
                                <text xml:lang='en'>My nurse&apos;s birthday!</text>
                            </activity>
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
