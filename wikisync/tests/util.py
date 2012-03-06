# -*- coding: utf-8 -*-
import unittest, os
from wikisync.util import str_mask, str_unmask, \
    parse_recent_changes, parse_timeline, parse_wiki, parse_form_params
from pkg_resources import resource_filename

class HTMLParserTestCase(unittest.TestCase):
    
    def _read_html(self, name):
        file = resource_filename(__name__, name)
        with open(file, "rb") as f:
            return f.read()

    def test_parse_form_params(self):
        source = self._read_html("Form.default.html")
        results = parse_form_params(source, form_id="edit")
        expected = {
            "comment": "", 
            "save": "Submit changes", 
            "preview": "Preview Page", 
            "text": "\nNew Page 1", 
            "readonly": "", 
            "cancel": "Cancel", 
            "__FORM_TOKEN": "14eedb9ed7cd519f6b34a5e6", 
            "version": "2", 
            "action": "edit", 
            "diff": "Review Changes", 
            "from_editor": "1", 
            "scroll_bar_pos": "", 
            "sidebyside": ""
        }
        for k, v in expected.items():
            self.assertEquals(results[k], v)
        
    def test_parse_recent_changes_edgewall(self):
        source = self._read_html("RecentChanges.edgewall.html")
        results = parse_recent_changes(source, path_prefix="/wiki")
        self.assertEqual(len(results), 696)

    def test_parse_recent_changes_default(self):
        source = self._read_html("RecentChanges.default.html")
        results = parse_recent_changes(source, path_prefix="/trac/wiki")
        self.assertEqual(len(results), 57)

    def test_parse_timeline_edgewall(self):
        source = self._read_html("Timeline.edgewall.html")
        results = parse_timeline(source, path_prefix="/wiki")
        self.assertEqual(len(results), 30)

    def test_parse_timeline_default(self):
        source = self._read_html("Timeline.default.html")
        results = parse_timeline(source, path_prefix="/trac/wiki")
        self.assertEqual(len(results), 57)

    def test_parse_wiki_edgewall(self):
        source = self._read_html("WikiStart.edgewall.html")
        results = parse_wiki(source, path_prefix="/wiki")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["remote_version"], 147)
        self.assertEqual(results[0]["name"], "WikiStart")

    def test_parse_wiki_default(self):
        source = self._read_html("WikiStart.default.html")
        results = parse_wiki(source, path_prefix="/trac/wiki")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["remote_version"], 2)
        self.assertEqual(results[0]["name"], "WikiStart")
        
class StringMaskTestCase(unittest.TestCase):
    
    def test_mask(self):
        message = "Hello World!"
        masked = str_mask(message)
        self.assertEqual(message, str_unmask(masked))
        self.assertRaises(ValueError, str_unmask, "clear text")
        
def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(HTMLParserTestCase, "test"))
    suite.addTest(unittest.makeSuite(StringMaskTestCase, "test"))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="suite")