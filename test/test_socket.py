import socket
import struct
from functools import reduce
from operator import xor
from tornado import gen
from tornado.iostream import IOStream
from tornado.log import app_log
from tornado.stack_context import NullContext
from tornado.tcpserver import TCPServer
from tornado.testing import AsyncTestCase, ExpectLog, bind_unused_port, gen_test

from tornado_server import StatusServer, NotifyServer

# Header
HEADER = 0x01
# Statuses
IDLE = 0x01
ACTIVE = 0x02
RECHARGE = 0x03

MESSAGE_NUM = struct.pack('>H', 1)
TEST_SOURCE_NAME = 'valera01'.encode('ascii') 
NUM_FIELDS = struct.pack('>B', 1)
FIELD_NAME = '~~~~~~~1'.encode('ascii') 
FIELD_VALUE = struct.pack('>L', 1)


msg = [
    (HEADER).to_bytes(1, byteorder='big'),          # 1 байт - header (всегда 0x01)
    MESSAGE_NUM,        # 2 байта - номер сообщения в пределах данного подключения (беззнаковое целое)
    TEST_SOURCE_NAME,   # 8 байт - идентификатор источника (ascii-строка)
    (ACTIVE).to_bytes(1, byteorder='big'),
    NUM_FIELDS,
    FIELD_NAME,
    FIELD_VALUE
    ]

msg1 = b''.join(msg)
bytes_arr = memoryview(msg1).cast('B')
msg.append(struct.pack('>B', reduce(xor, msg1)))
msg1 = b''.join(msg)


class TCPServerTest(AsyncTestCase):
    @gen_test
    def test_message_response(self):
        # handle_stream may be a coroutine and any exception in its
        # Future will be logged.
        server = client = None
        try:
            sock, port = bind_unused_port()
            sock2, port2 = bind_unused_port()

            with NullContext():
                server = StatusServer()

                notify_server = NotifyServer()
                notify_server.add_socket(sock2)

                server.notify_server = notify_server

                server.add_socket(sock)

            client = IOStream(socket.socket())        
            yield client.connect(('localhost', port))
            yield client.write(msg1)
            results = yield client.read_bytes(4)
            assert results == b'\x11\x00\x01\x10'

        finally:
            if server is not None:
                server.stop()
            if client is not None:
                client.close()

    # @gen_test
    # def test_notify(self):
    #     # handle_stream may be a coroutine and any exception in its
    #     # Future will be logged.
    #     server = client = None
    #     try:
    #         sock, port = bind_unused_port()
    #         sock2, port2 = bind_unused_port()

    #         with NullContext():
    #             server = StatusServer()
    #             server.add_socket(sock)
                
    #             notify_server = NotifyServer()
    #             notify_server.add_socket(sock2)

    #             server.notify_server = notify_server


    #         client = IOStream(socket.socket())
    #         client2 = IOStream(socket.socket()) 
            
    #         yield client2.connect(('localhost', port2))            
    #         yield client.connect(('localhost', port))
    #         yield client.write(msg)
    #         results = yield client.read_bytes(4)
    #         results2 = yield client2.read_bytes(1023)
    #         client.close()
    #         client2.close()
    #         assert results == b'\x11\x00\x01\x10'
    #         assert results2 == b'[valera01]~~~~~~~1|\x00\x00\x00\x01\n'

    #     finally:
    #         if server is not None:
    #             server.stop()
    #         if client is not None:
    #             client.close()
