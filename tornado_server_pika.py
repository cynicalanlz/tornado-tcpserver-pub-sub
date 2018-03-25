import uuid
import json
import time
from operator import xor
import logging
from logging.handlers import RotatingFileHandler
from functools import reduce
from itertools import zip_longest
import struct

from tornado.process import fork_processes
from tornado.ioloop import IOLoop
from tornado.iostream import IOStream
from tornado.tcpserver import TCPServer
from tornado.iostream import StreamClosedError
from tornado.log import enable_pretty_logging
from tornado.netutil import bind_sockets

import pika
from pika.adapters import TornadoConnection
pika.log = logging.getLogger(__name__)


enable_pretty_logging()



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

class PikaClient(object):
 
    def __init__(self, io_loop):
        pika.log.info('PikaClient: __init__')
        self.io_loop = io_loop
 
        self.connected = False
        self.connecting = False
        self.connection = None
        self.channel = None
 
        self.event_listeners = set([])
 
    def connect(self):
        if self.connecting:
            pika.log.info('PikaClient: Already connecting to RabbitMQ')
            return
 
        pika.log.info('PikaClient: Connecting to RabbitMQ')
        self.connecting = True
 
        cred = pika.PlainCredentials('guest', 'guest')
        param = pika.ConnectionParameters(
            host='localhost',
            port=5672,
            virtual_host='/',
            credentials=cred
        )
 
        self.connection = TornadoConnection(
            param,
            on_open_callback=self.on_connected)
        self.connection.add_on_close_callback(self.on_closed)
 
    def on_connected(self, connection):
        pika.log.info('PikaClient: connected to RabbitMQ')
        self.connected = True
        self.connection = connection
        self.connection.channel(self.on_channel_open)
 
    def on_channel_open(self, channel):
        pika.log.info('PikaClient: Channel open, Declaring exchange')
        self.channel = channel
        # declare exchanges, which in turn, declare
        # queues, and bind exchange to queues
 
    def on_closed(self, connection):
        pika.log.info('PikaClient: rabbit connection closed')
        self.io_loop.stop()



class Connection(object):
    def __init__(self, stream, address, connections, pc):

        logger.info('receive a new connection from %s', address)
        self.state = 'AUTH'
        self.connections = connections
        self.stream = stream
        self.address = address
        self.stream.set_close_callback(self._on_close)
        self.stream.read_bytes(13, self._on_read_header, partial=True)
        self.last_message_time = int(round(time.time() * 1000))
        self.fields = {}
        self.pc = pc


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

    def _notify_about_message(self):
        body  = json.dumps({
            'message_number' : self.message_number,
            'uid' : self.uid,
            'status' : self.status,
            'fields_num' : self.fields_num,
            'fields' : self.fields
            })
        # logger.info(self.pc, self.pc.channel)
        if self.pc.channel != None:
            self.pc.channel.basic_publish(
                exchange='consumers_stats',
                routing_key=self.uid,
                body=body)
    

    def _on_write_complete(self):
        logger.info('answered %s', self.address)
        self.response_msg = ''
        self._notify_about_message()
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
            Connection(stream, address, conns, self.pc)
        except StreamClosedError:
            pass

def main(conns):
    io_loop = IOLoop.instance()
    pc = PikaClient(io_loop)
    server = StatusServer()
    server.pc = pc
    server.pc.connect()
    server.listen(8888)
    io_loop.start()

conns = {}

if __name__ == '__main__':
    main(conns)