#! /usr/bin/env python3

from unittest import TestCase
from io import BytesIO, BufferedReader
from errno import ECONNREFUSED
import net
import urllib.request
import http.client
from unittest.mock import patch

class Test(TestCase):
    def test_format_addr(self):
        tests = (
            ("::1", 80, "[::1]:80"),
            ("::1", None, "[::1]"),
            ("localhost", 0, "localhost:0"),
            ("localhost", None, "localhost"),
        )
        for [host, port, output] in tests:
            input = (host, port)
            with self.subTest(input):
                self.assertEqual(output, net.format_addr(input))

class TestPersistentHttp(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.handler = net.PersistentConnectionHandler()
        self.addCleanup(self.handler.close)
        self.urlopen = urllib.request.build_opener(self.handler).open

class TestLoopbackHttp(TestPersistentHttp):
    def setUp(self):
        from http.server import HTTPServer, BaseHTTPRequestHandler
        from threading import Thread
        
        class RequestHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            
            def do_GET(handler):
                if handler.path == "/close-if-reused" and handler.reused:
                    handler.close_connection = True
                    return
                handler.send_response(200)
                handler.send_header("Content-Length", format(6))
                handler.end_headers()
                handler.wfile.write(b"body\r\n")
                handler.reused = True
            
            def do_POST(handler):
                if handler.path == "/close-if-reused" and handler.reused:
                    handler.close_connection = True
                    return
                length = int(handler.headers["Content-Length"])
                while length > 0:
                    length -= len(handler.rfile.read(min(length, 0x10000)))
                handler.do_GET()
            
            self.handle_calls = 0
            def handle(handler, *pos, **kw):
                self.handle_calls += 1
                handler.reused = False
                return BaseHTTPRequestHandler.handle(handler, *pos, **kw)
        
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
        with self.urlopen(self.url + "/initial-request") as response:
            self.assertEqual(b"body\r\n", response.read())
        self.assertEqual(1, self.handle_calls, "Server handle() not called")
        
        with self.urlopen(self.url + "/second-request") as response:
            self.assertEqual(b"body\r\n", response.read())
        self.assertEqual(1, self.handle_calls, "Unexpected handle() call")
    
    def test_close_empty(self):
        """Test connection closure seen as empty response"""
        with self.urlopen(self.url + "/initial-request") as response:
            self.assertEqual(b"body\r\n", response.read())
        self.assertEqual(1, self.handle_calls, "Server handle() not called")
        
        # Idempotent request should be retried
        with self.urlopen(self.url + "/close-if-reused") as response:
            self.assertEqual(b"body\r\n", response.read())
        self.assertEqual(2, self.handle_calls, "Server handle() not called")
        
        # Non-idempotent request should not be retried
        with self.assertRaises(http.client.BadStatusLine):
            self.urlopen(self.url + "/close-if-reused", b"data")
        self.assertEqual(2, self.handle_calls, "Server handle() retried")
    
    def test_close_error(self):
        """Test connection closure reported as connection error"""
        self.close_connection = True
        with self.urlopen(self.url + "/initial-request") as response:
            self.assertEqual(b"body\r\n", response.read())
        self.assertEqual(1, self.handle_calls, "Server handle() not called")
        
        data = b"3" * 3000000
        with self.assertRaises(http.client.BadStatusLine):
            self.urlopen(self.url + "/close-if-reused", data)
        self.assertEqual(1, self.handle_calls, "Server handle() retried")

class TestMockHttp(TestPersistentHttp):
    def setUp(self):
        super().setUp()
        entry = {"mock": self.HTTPConnection}
        patcher = patch.dict(self.handler.conn_classes, entry)
        patcher.start()
        self.addCleanup(patcher.stop)

def select_timeout(*pos, **kw):
    return ([], [], [])

@patch("net.select", select_timeout)
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
            self.reader.fileno = lambda: None
        def sendall(self, *pos, **kw):
            pass
        def close(self, *pos, **kw):
            self.data = None
        def makefile(self, *pos, **kw):
            return self.reader
    
    def test_reuse(self):
        """Test existing connection is reused"""
        with self.urlopen("mock://localhost/one") as response:
            self.assertEqual(b"First body\r\n", response.read())
        sock = self.handler._connection.sock
        self.assertTrue(sock.reader, "Disconnected after first request")
        
        with self.urlopen("mock://localhost/two") as response:
            self.assertEqual(b"Second body\r\n", response.read())
        self.assertIs(sock, self.handler._connection.sock,
            "Socket connection changed")
        self.assertTrue(sock.reader, "Disconnected after second request")
    
    def test_new_host(self):
        """Test connecting to second host"""
        with self.urlopen("mock://localhost/one") as response:
            self.assertEqual(b"First body\r\n", response.read())
        sock1 = self.handler._connection.sock
        self.assertTrue(sock1.reader, "Disconnected after first request")
        
        with self.urlopen("mock://otherhost/two") as response:
            self.assertEqual(b"First body\r\n", response.read())
        sock2 = self.handler._connection.sock
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
            self.urlopen("mock://dummy")
        except http.client.HTTPException:
            raise
        except EnvironmentError as err:
            if err.errno != ECONNREFUSED:
                raise
        else:
            self.fail("ECONNREFUSED not raised")
        self.assertEqual(1, self.handler._connection.connect_count)
