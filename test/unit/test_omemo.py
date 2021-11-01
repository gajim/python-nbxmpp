
import unittest
from test.lib.client import TestClient
from test.lib.util import iterate_mainloop

import unicodedata

class OMEMOTest(unittest.TestCase):

    def test_omemo(self):
        flow = ['''
            <iq type='result' to='testclient@unittest.com/test' id='1'>
                <pubsub xmlns='http://jabber.org/protocol/pubsub'>
                    <publish node='eu.siacs.conversations.axolotl.devicelist'>
                        <item id='current'/>
                    </publish>
                </pubsub>
            </iq>''',
        ]

        client = TestClient(flow)

        task = client.get_module('OMEMO').set_devicelist(['123'])

        iterate_mainloop()

        self.assertTrue(task.state.is_finished)
        result = task.finish()
        self.assertTrue(result.node == 'eu.siacs.conversations.axolotl.devicelist')
        self.assertTrue(result.id == 'current')
