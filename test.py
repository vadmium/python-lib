#! /usr/bin/env python3

from unittest import TestCase
from io import BytesIO

import iview.utils
import urllib.request

class TestPersistentHttp(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.connection = iview.utils.PersistentConnectionHandler()
        self.addCleanup(self.connection.close)
        self.session = urllib.request.build_opener(self.connection)

class TestLoopbackHttp(TestPersistentHttp):
    def setUp(self):
        from http.server import HTTPServer, BaseHTTPRequestHandler
        from threading import Thread
        
        class RequestHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            
            self.close_connection = False
            def do_GET(handler):
                handler.send_response(200)
                handler.send_header("Content-Length", format(6))
                handler.end_headers()
                handler.wfile.write(b"body\r\n")
                handler.close_connection = self.close_connection
            
            self.handle_calls = 0
            def handle(*pos, **kw):
                self.handle_calls += 1
                return BaseHTTPRequestHandler.handle(*pos, **kw)
        
        server = HTTPServer(("localhost", 0), RequestHandler)
        self.addCleanup(server.server_close)
        self.url = "http://localhost:{}".format(server.server_port)
        thread = Thread(target=server.serve_forever)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        return TestPersistentHttp.setUp(self)

    def test_reuse(self):
        """Test existing connection is reused"""
        with self.session.open(self.url + "/one") as response:
            self.assertEqual(b"body\r\n", response.read())
        self.assertEqual(1, self.handle_calls, "Server handle() not called")
        
        with self.session.open(self.url + "/two") as response:
            self.assertEqual(b"body\r\n", response.read())
        self.assertEqual(1, self.handle_calls, "Unexpected handle() call")
    
    def test_close_empty(self):
        """Test connection closure seen as empty response"""
        self.close_connection = True
        with self.session.open(self.url + "/one") as response:
            self.assertEqual(b"body\r\n", response.read())
        self.assertEqual(1, self.handle_calls,
            "Server handle() not called for /one")
        
        with self.session.open(self.url + "/two") as response:
            self.assertEqual(b"body\r\n", response.read())
        self.assertEqual(2, self.handle_calls,
            "Server handle() not called for /two")

import http.client

class TestMockHttp(TestPersistentHttp):
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
    
    def run(self, *pos, **kw):
        with substattr(iview.utils, self.HTTPConnection):
            return TestPersistentHttp.run(self, *pos, **kw)
    
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
