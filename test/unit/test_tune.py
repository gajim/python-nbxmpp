from test.lib.util import StanzaHandlerTest

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import PubSubEventData
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import TuneData


class TuneTest(StanzaHandlerTest):

    def test_tune_parsing(self):
        def _on_message(_con, _stanza, properties):

            data = TuneData(
                artist="Yes",
                length="686",
                rating="8",
                source="Yessongs",
                title="Heart of the Sunrise",
                track="3",
                uri="https://www.artist.com",
            )

            pubsub_event = PubSubEventData(
                node="http://jabber.org/protocol/tune",
                id="bffe6584-0f9c-11dc-84ba-001143d5d5db",
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
                    <items node='http://jabber.org/protocol/tune'>
                        <item id='bffe6584-0f9c-11dc-84ba-001143d5d5db'>
                            <tune xmlns='http://jabber.org/protocol/tune'>
                                <artist>Yes</artist>
                                <length>686</length>
                                <rating>8</rating>
                                <source>Yessongs</source>
                                <title>Heart of the Sunrise</title>
                                <track>3</track>
                                <uri>https://www.artist.com</uri>
                            </tune>
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
