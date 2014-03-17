#! /usr/bin/env python3

from unittest import TestCase
from io import BytesIO

import http.client
import iview.utils
import urllib.request

class TestMockHttp(TestCase):
    class HTTPConnection(http.client.HTTPConnection):
        def __init__(self, host):
            http.client.HTTPConnection.__init__(self, host)
        
        def connect(self):
            self.sock = TestMockHttp.Socket(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Length: 6\r\n"
                b"\r\n"
                b"body\r\n"
            )
    
    class Socket:
        def __init__(self, data):
            self.data = data
        def sendall(self, *pos, **kw):
            pass
        def close(self, *pos, **kw):
            self.data = None
        def makefile(self, *pos, **kw):
            return BytesIO(self.data)
    
    def setUp(self):
        self.connection = iview.utils.PersistentConnectionHandler()
        self.addCleanup(self.connection.close)
        self.session = urllib.request.build_opener(self.connection)
    
    def run(self, *pos, **kw):
        with substattr(iview.utils, self.HTTPConnection):
            return TestCase.run(self, *pos, **kw)
    
    def test_reuse(self):
        """Test existing connection is reused"""
        with self.session.open("http://localhost/one") as response:
            self.assertEqual(b"body\r\n", response.read())
        sock = self.connection._connection.sock
        self.assertTrue(sock.data, "Disconnected after first request")
        
        with self.session.open("http://localhost/two") as response:
            self.assertEqual(b"body\r\n", response.read())
        self.assertIs(sock, self.connection._connection.sock,
            "Socket connection changed")
        self.assertTrue(sock.data, "Disconnected after second request")
    
    def test_new_host(self):
        """Test connecting to second host"""
        with self.session.open("http://localhost/one") as response:
            self.assertEqual(b"body\r\n", response.read())
        sock1 = self.connection._connection.sock
        self.assertTrue(sock1.data, "Disconnected after first request")
        
        with self.session.open("http://otherhost/two") as response:
            self.assertEqual(b"body\r\n", response.read())
        sock2 = self.connection._connection.sock
        self.assertIsNot(sock1, sock2, "Expected new socket connection")
        self.assertTrue(sock2.data, "Disconnected after second request")
