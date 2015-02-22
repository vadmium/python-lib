#! /usr/bin/env python3

from unittest import TestCase
from io import BytesIO, BufferedReader
from errno import ECONNREFUSED
import net
import urllib.request
import http.client
from unittest.mock import patch

class TestPersistentHttp(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.connection = net.PersistentConnectionHandler()
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
            
            def do_POST(handler):
                length = int(handler.headers["Content-Length"])
                while length > 0:
                    length -= len(handler.rfile.read(min(length, 0x10000)))
                
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
        
        # Idempotent request should be retried
        with self.session.open(self.url + "/two") as response:
            self.assertEqual(b"body\r\n", response.read())
        self.assertEqual(2, self.handle_calls,
            "Server handle() not called for /two")
        
        # Non-idempotent request should not be retried
        with self.assertRaises(http.client.BadStatusLine):
            self.session.open(self.url + "/post", b"data")
        self.assertEqual(2, self.handle_calls,
            "Server handle() retried for POST")
    
    def test_close_error(self):
        """Test connection closure reported as connection error"""
        self.close_connection = True
        with self.session.open(self.url + "/one") as response:
            self.assertEqual(b"body\r\n", response.read())
        self.assertEqual(1, self.handle_calls,
            "Server handle() not called for /one")
        
        data = b"3" * 3000000
        with self.assertRaises(http.client.BadStatusLine):
            self.session.open(self.url + "/two", data)
        self.assertEqual(1, self.handle_calls,
            "Server handle() retried for POST")

class TestMockHttp(TestPersistentHttp):
    def setUp(self):
        super().setUp()
        patcher = patch("http.client.HTTPConnection", self.HTTPConnection)
        patcher.start()
        self.addCleanup(patcher.stop)

class TestHttpSocket(TestMockHttp):
    class HTTPConnection(http.client.HTTPConnection):
        def connect(self):
            self.sock = TestHttpSocket.Socket(
                b"HTTP/1.1 200 First response\r\n"
                b"Content-Length: 12\r\n"
                b"\r\n"
                b"First body\r\n"
                
                b"HTTP/1.1 200 Second response\r\n"
                b"Content-Length: 13\r\n"
                b"\r\n"
                b"Second body\r\n"
            )
    
    class Socket:
        def __init__(self, data):
            self.reader = BufferedReader(BytesIO(data))
            self.reader.close = lambda: None  # Avoid Python Issue 23377
        def sendall(self, *pos, **kw):
            pass
        def close(self, *pos, **kw):
            self.data = None
        def makefile(self, *pos, **kw):
            return self.reader
    
    def test_reuse(self):
        """Test existing connection is reused"""
        with self.session.open("http://localhost/one") as response:
            self.assertEqual(b"First body\r\n", response.read())
        sock = self.connection._connection.sock
        self.assertTrue(sock.reader, "Disconnected after first request")
        
        with self.session.open("http://localhost/two") as response:
            self.assertEqual(b"Second body\r\n", response.read())
        self.assertIs(sock, self.connection._connection.sock,
            "Socket connection changed")
        self.assertTrue(sock.reader, "Disconnected after second request")
    
    def test_new_host(self):
        """Test connecting to second host"""
        with self.session.open("http://localhost/one") as response:
            self.assertEqual(b"First body\r\n", response.read())
        sock1 = self.connection._connection.sock
        self.assertTrue(sock1.reader, "Disconnected after first request")
        
        with self.session.open("http://otherhost/two") as response:
            self.assertEqual(b"First body\r\n", response.read())
        sock2 = self.connection._connection.sock
        self.assertIsNot(sock1, sock2, "Expected new socket connection")
        self.assertTrue(sock2.reader, "Disconnected after second request")

class TestHttpEstablishError(TestMockHttp):
    """Connection establishment errors should not trigger a retry"""
    class HTTPConnection(http.client.HTTPConnection):
        def __init__(self, *pos, **kw):
            self.connect_count = 0
            super().__init__(*pos, **kw)
        def connect(self):
            self.connect_count += 1
            raise self.connect_exception
    
    def test_refused(self):
        exception = EnvironmentError(ECONNREFUSED, "Mock connection refusal")
        self.HTTPConnection.connect_exception = exception
        try:
            self.session.open("http://dummy")
        except http.client.HTTPException:
            raise
        except EnvironmentError as err:
            if err.errno != ECONNREFUSED:
                raise
        else:
            self.fail("ECONNREFUSED not raised")
        self.assertEqual(1, self.connection._connection.connect_count)
