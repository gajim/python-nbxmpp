from test.lib.util import StanzaHandlerTest

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import MoodData
from nbxmpp.structs import PubSubEventData


class MoodTest(StanzaHandlerTest):

    def test_mood_parsing(self):
        def _on_message(_con, _stanza, properties):

            data = MoodData(mood='annoyed', text='curse my nurse!')

            pubsub_event = PubSubEventData(
                node='http://jabber.org/protocol/mood',
                id='a475804a-0f9c-11dc-98a8-001143d5d5db',
                item=None,
                data=data,
                deleted=False,
                retracted=False,
                purged=False)

            # We cant compare Node objects
            pubsub_event_ = properties.pubsub_event._replace(item=None)
            self.assertEqual(pubsub_event, pubsub_event_)

        event = '''
            <message from='test@test.test'>
                <event xmlns='http://jabber.org/protocol/pubsub#event'>
                    <items node='http://jabber.org/protocol/mood'>
                        <item id='a475804a-0f9c-11dc-98a8-001143d5d5db'>
                            <mood xmlns='http://jabber.org/protocol/mood'>
                                <annoyed/>
                                <text>curse my nurse!</text>
                            </mood>
                        </item>
                    </items>
                </event>
            </message>
        '''

        self.dispatcher.register_handler(
            StanzaHandler(name='message',
                          callback=_on_message,
                          ns=Namespace.PUBSUB_EVENT))

        self.dispatcher.process_data(event)
