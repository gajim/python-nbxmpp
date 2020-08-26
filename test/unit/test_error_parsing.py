import unittest

from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.util import error_factory


class TestErrorParsing(unittest.TestCase):

    def test_error_parsing(self):
        stanza = '''
        <iq from='upload.montague.tld'
            id='step_03'
            to='romeo@montague.tld/garden'
            type='error'>
          <error type='modify'>
            <not-acceptable xmlns='urn:ietf:params:xml:ns:xmpp-stanzas' />
            <text xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'>File too large. The maximum file size is 20000 bytes</text>
            <text xml:lang='de' xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'>File zu groß. Erlaubt sind 20000 bytes</text>
            <file-too-large xmlns='urn:xmpp:http:upload:0'>
              <max-file-size>20000</max-file-size>
            </file-too-large>
          </error>
        </iq>'''

        error = error_factory(Iq(node=stanza))
        self.assertEqual(error.condition, 'not-acceptable')
        self.assertEqual(error.app_condition, 'file-too-large')
        self.assertEqual(error.get_text(), 'File too large. The maximum file size is 20000 bytes')
        self.assertEqual(error.get_text('de'), 'File zu groß. Erlaubt sind 20000 bytes')
        self.assertEqual(error.type, 'modify')
        self.assertEqual(error.id, 'step_03')
        self.assertEqual(error.jid, JID.from_string('upload.montague.tld'))
