import time
import logging
from logging.handlers import RotatingFileHandler

import struct
from tornado.process import fork_processes
from tornado.ioloop import IOLoop
from tornado.iostream import IOStream
from tornado.tcpserver import TCPServer
from tornado.iostream import StreamClosedError
from tornado.log import enable_pretty_logging
from tornado.netutil import bind_sockets
from operator import xor
from functools import reduce
from itertools import zip_longest

enable_pretty_logging()

import uuid

LOG_FILENAME = 'api.log'
fileHandler = RotatingFileHandler(
    LOG_FILENAME, maxBytes=1024*1024*1024,
    backupCount=5, encoding='utf-8')
fileHandler.setLevel(logging.DEBUG)
filefmt = '%(asctime)s [%(filename)s:%(lineno)d] %(message)s'
fileFormatter = logging.Formatter(filefmt)
fileHandler.setFormatter(fileFormatter)

logger = logging.getLogger(__name__)
logger.addHandler(fileHandler)

access_log = logging.getLogger("tornado.access")
app_log = logging.getLogger("tornado.application")
gen_log = logging.getLogger("tornado.general")

access_log.addHandler(fileHandler)
app_log.addHandler(fileHandler)
gen_log.addHandler(fileHandler)


SUCCESS = 0x11
FAILTURE = 0x12

class Connection(object):
    def __init__(self, stream, address, connections):

        logger.info('receive a new connection from %s', address)
        self.state = 'AUTH'
        self.connections = connections
        self.stream = stream
        self.address = address
        self.stream.set_close_callback(self._on_close)
        self.stream.read_bytes(13, self._on_read_header, partial=True)
        self.last_message_time = int(round(time.time() * 1000))
        self.fields = {}


    def _on_read_header(self, data):
        logger.info('got a new message from %s - %s', self.address, data)

        self.message_number = struct.unpack('>H',data[1:3])[0]      
        self.uid = data[3:11].decode('ascii')
        self.status = data[11]
        self.fields_num = data[12]


        logger.info('msg_num: {}, uid: {}, status: {}, fields_num: {}'.format(
            self.message_number,
            self.uid,
            self.status,
            self.fields_num,
            ))

        if self.state == 'AUTH':
            self.connections[self.uid] = self
            self.state = 'AUTHENTICATED'
            logger.info('%s authenticated\n' % (self.uid))


        msg = [
            (SUCCESS).to_bytes(1, byteorder='big'),
            struct.pack('>H', self.message_number)
        ]
        self._calculate_response(msg)
        
        if self.fields_num == 0:
            self._read_more()
        
        self.stream.read_bytes(self.fields_num*12, self._on_read_fields, partial=True)        

    def _calculate_response(self, msg):
        msg_xor = b''.join(msg)
        bytes_arr = memoryview(msg_xor).cast('B')
        msg.append( struct.pack('>B', reduce(xor, msg_xor)))
        msg = b''.join(msg)
        self.response_msg = msg

    def _on_read_fields(self, data):
        logger.info('got a new message from %s - %s', self.address, data)

        ends = [(x+1)*13 for x in range(self.fields_num)]
        starts = [x-13 for x in ends]
        for message_start, message_finish in zip_longest(starts, ends):
            mess = data[message_start:message_finish]
            name = mess[0:8].decode('ascii')
            value = struct.unpack('>L', mess[8:12])
            self.fields[name] = value
        self._read_more() 


    def _on_write_complete(self):
        logger.info('answered %s', self.address)
        self.response_msg = ''
        if not self.stream.reading():
            self.stream.read_bytes(13, self._on_read_header)

    def _read_more(self):
        if self.response_msg == '':
            self._on_write_complete()

        self.stream.write(self.response_msg, self._on_write_complete)

    
    def _on_close(self):
        logger.info('client quit %s - %s', self.address, self.uid)
        if self.uid != None:
            del self.connections[self.uid]

class StatusServer(TCPServer):
    
    def __init__(self, ssl_options=None, **kwargs):
        logger.info('connection monitoring app started')
        TCPServer.__init__(self, ssl_options=ssl_options, **kwargs)


    def handle_stream(self, stream, address):
        try:
            Connection(stream, address, conns)
        except StreamClosedError:
            pass

def main(conns):
    # sockets = bind_sockets(8888)
    # fork_processes(0)
    # server = StatusServer()
    # server.add_sockets(sockets)
    # IOLoop.current().start()

    server = StatusServer()
    server.listen(8888)
    IOLoop.instance().start()

conns = {}

if __name__ == '__main__':
    main(conns)