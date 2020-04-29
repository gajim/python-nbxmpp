from test.lib.util import StanzaHandlerTest

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import LocationData
from nbxmpp.structs import PubSubEventData


class LocationTest(StanzaHandlerTest):

    def test_location_parsing(self):
        def _on_message(_con, _stanza, properties):

            data = LocationData(accuracy='20',
                                alt='1609',
                                altaccuracy='10',
                                area='Central Park',
                                bearing='12.33',
                                building='The Empire State Building',
                                country='United States',
                                countrycode='US',
                                datum='Some datum',
                                description='Bill\'s house',
                                error='290.8882087',
                                floor='102',
                                lat='39.75',
                                locality='New York City',
                                lon='-104.99',
                                postalcode='10118',
                                region='New York',
                                room='Observatory',
                                speed='52.69',
                                street='350 Fifth Avenue / 34th and Broadway',
                                text='Northwest corner of the lobby',
                                timestamp='2004-02-19T21:12Z',
                                tzo='-07:00',
                                uri='http://www.nyc.com/')

            pubsub_event = PubSubEventData(
                node='http://jabber.org/protocol/geoloc',
                id='d81a52b8-0f9c-11dc-9bc8-001143d5d5db',
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
                    <items node='http://jabber.org/protocol/geoloc'>
                        <item id='d81a52b8-0f9c-11dc-9bc8-001143d5d5db'>
                            <geoloc xmlns='http://jabber.org/protocol/geoloc' xml:lang='en'>
                                <accuracy>20</accuracy>
                                <alt>1609</alt>
                                <altaccuracy>10</altaccuracy>
                                <area>Central Park</area>
                                <bearing>12.33</bearing>
                                <building>The Empire State Building</building>
                                <country>United States</country>
                                <countrycode>US</countrycode>
                                <datum>Some datum</datum>
                                <description>Bill's house</description>
                                <error>290.8882087</error>
                                <floor>102</floor>
                                <lat>39.75</lat>
                                <locality>New York City</locality>
                                <lon>-104.99</lon>
                                <postalcode>10118</postalcode>
                                <region>New York</region>
                                <room>Observatory</room>
                                <speed>52.69</speed>
                                <street>350 Fifth Avenue / 34th and Broadway</street>
                                <text>Northwest corner of the lobby</text>
                                <timestamp>2004-02-19T21:12Z</timestamp>
                                <tzo>-07:00</tzo>
                                <uri>http://www.nyc.com/</uri>
                            </geoloc>
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
