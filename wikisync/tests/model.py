# -*- coding: utf-8 -*-
import unittest
from wikisync.plugin import WikiSyncEnvironment
from wikisync.model import WikiSyncDao
from trac.test import EnvironmentStub
from pkg_resources import resource_filename

class WikiSyncModelTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.plugin = WikiSyncEnvironment(self.env)
        self.plugin.upgrade_environment(self.env.get_db_cnx())
        self.dao = WikiSyncDao(self.env)
        file = resource_filename(__name__, "data.sql")
        @self.env.with_transaction()
        def do_save(db):
            cursor = db.cursor()
            with open(file, "rb") as f:
                for sql in f:
                    if sql:
                        cursor.execute(sql)
    
    def test_sync_wiki_data(self):
        self.dao.sync_wiki_data()
        for name in ["CamelCase", "InterMapTxt", "NewPage", "WikiRestructuredTextLinks"]:
            self.assertTrue(self.dao.find(name) is not None)
            
    def test_all(self):
        results = [item for item in self.dao.all()]
        self.assertEqual(len(results), 3)

    def test_validate(self):
        item = self.dao.factory()
        self.assertRaises(AssertionError, item.validate)
        item.merge(name="Test").validate()

    def test_read(self):
        item = self.dao.find("Test1")
        self.assertEqual(self.dao.find("Unknown"), None)
        
    def test_create(self):
        self.dao.create(
            self.dao.factory(
                name="Test2", 
                remote_version=2
            )
        )
        db = self.env.get_read_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT name, remote_version FROM wikisync
            WHERE name='Test2'
        """)
        results = cursor.fetchall()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], (u'Test2', 2))

    def test_delete(self):
        item = self.dao.find("Test1") 
        self.assertTrue(item is not None)
        self.dao.delete(item)
        self.assertTrue(self.dao.find("Test1") is None)
        
    def test_update(self):
        item = self.dao.find("Test1")
        item = item.merge(sync_remote_version=1, remote_version=11)
        self.dao.update(item)
        db = self.env.get_read_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sync_remote_version, remote_version FROM wikisync
            WHERE name='Test1'
        """)
        results = cursor.fetchall()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], (1, 11))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(WikiSyncModelTestCase, 'test'))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="suite")