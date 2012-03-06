# -*- coding: utf-8 -*-
import unittest
from wikisync.util import WikiSyncRpc

class WikiSyncRpcTestCase(unittest.TestCase):
    
    def setUp(self):
        self.rpc = WikiSyncRpc("http://localhost:8000/trac-target", 
            "admin", "password", debug=True)
    
    def xtest_authentication(self):
        f = self.rpc.open("wiki/WikiStart")
        f.close()
    
    def test_get_remote_list(self):
        print self.rpc.get_remote_version("WikiStart")
        
def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(WikiSyncRpcTestCase, "test"))
    return suite

if __name__ == "__main__":
    unittest.main(defaultTest="suite")