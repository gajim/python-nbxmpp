from test.lib.util import StanzaHandlerTest

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import PubSubEventData


class PubsubTest(StanzaHandlerTest):

    def test_purge_event(self):
        def _on_message(_con, _stanza, properties):

            pubsub_event = PubSubEventData(
                node='princely_musings',
                id=None,
                item=None,
                data=None,
                deleted=False,
                retracted=False,
                purged=True)

            self.assertEqual(pubsub_event, properties.pubsub_event)

        event = '''
            <message from='test@test.test' id='b5ac48d0-0f9c-11dc-8754-001143d5d5db'>
                <event xmlns='http://jabber.org/protocol/pubsub#event'>
                    <purge node='princely_musings'/>
                </event>
            </message>
        '''

        self.dispatcher.register_handler(
            StanzaHandler(name='message',
                          callback=_on_message,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16))

        self.dispatcher.process_data(event)

    def test_delete_event(self):
        def _on_message(_con, _stanza, properties):

            pubsub_event = PubSubEventData(
                node='princely_musings',
                id=None,
                item=None,
                data=None,
                deleted=True,
                retracted=False,
                purged=False)

            self.assertEqual(pubsub_event, properties.pubsub_event)

        event = '''
            <message from='test@test.test' id='b5ac48d0-0f9c-11dc-8754-001143d5d5db'>
                <delete node='princely_musings'>
                    <redirect uri='xmpp:hamlet@denmark.lit?;node=blog'/>
                </delete>
            </message>
        '''

        self.dispatcher.register_handler(
            StanzaHandler(name='message',
                          callback=_on_message,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16))

        self.dispatcher.process_data(event)


    def test_retracted_event(self):
        def _on_message(_con, _stanza, properties):

            pubsub_event = PubSubEventData(
                node='princely_musings',
                id='ae890ac52d0df67ed7cfdf51b644e901',
                item=None,
                data=None,
                deleted=False,
                retracted=True,
                purged=False)

            self.assertEqual(pubsub_event, properties.pubsub_event)

        event = '''
            <message from='test@test.test' id='b5ac48d0-0f9c-11dc-8754-001143d5d5db'>
                <items node='princely_musings'>
                    <retract id='ae890ac52d0df67ed7cfdf51b644e901'/>
                </items>
            </message>
        '''

        self.dispatcher.register_handler(
            StanzaHandler(name='message',
                          callback=_on_message,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16))

        self.dispatcher.process_data(event)
