import unittest

from lxml import etree

from nbxmpp.builder import E
from nbxmpp.elements import Base


build_lookup = etree.ElementDefaultClassLookup(element=Base)
build_parser = etree.XMLParser()
build_parser.set_element_class_lookup(build_lookup)


class ElementTest(unittest.TestCase):

    def test_e_builder(self):
        parsed = etree.fromstring('<a xmlns="j:a"><b/><c xmlns="j:c"/></a>', build_parser)
        build = E('a', namespace='j:a')
        build.add_tag('b')
        build.add_tag('c', namespace='j:c')

        self.assertTrue(parsed.tag == build.tag)
        self.assertTrue(parsed.nsmap == build.nsmap)

        for x in range(2):
            self.assertTrue(parsed[x].tag == build[x].tag)
            self.assertTrue(parsed[x].nsmap == build[x].nsmap)

    def test_find_tag(self):
        element = etree.fromstring('<a xmlns="j:a"><b/><c xmlns="j:c"/></a>', build_parser)

        self.assertIsNotNone(element.find_tag('b'))
        self.assertIsNotNone(element.find_tag('b', namespace='j:a'))

        self.assertIsNone(element.find_tag('c'))
        self.assertIsNone(element.find_tag('c', namespace='j:a'))

    def test_add_tag(self):
        element = E('a', namespace='j:a')
        element.add_tag('b', namespace='j:b')
        self.assertTrue('<a xmlns="j:a"><b xmlns="j:b"/></a>' == element.tostring())

        element_b = element.find_tag('b')
        self.assertIsNone(element_b)

        element_b = element.find_tag('b', namespace='j:b')
        self.assertTrue(element_b.tag == '{j:b}b')

        element = E('a', namespace='j:a')
        element.add_tag('b')
        self.assertTrue('<a xmlns="j:a"><b/></a>' == element.tostring())

        element_b = element.find_tag('b')
        self.assertTrue(element_b.tag == '{j:a}b')
        self.assertTrue(element_b.namespace == 'j:a')

        element_b = element.find_tag('b', namespace='j:a')
        self.assertTrue(element_b.tag == '{j:a}b')
        self.assertTrue(element_b.namespace == 'j:a')

    def test_add_tag_text(self):
        element = E('a', namespace='j:a')
        element.add_tag_text('b', 'test')
        self.assertTrue('<a xmlns="j:a"><b>test</b></a>' == element.tostring())

        element_b = element.find_tag('b')
        self.assertTrue(isinstance(element_b, Base))

        element = E('a', namespace='j:a')
        element.add_tag_text('b', 'test', namespace='j:b')
        self.assertTrue('<a xmlns="j:a"><b xmlns="j:b">test</b></a>' == element.tostring())

        element_b = element.find_tag('b', namespace='j:b')
        self.assertTrue(isinstance(element_b, Base))
