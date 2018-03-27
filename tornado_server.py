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
    def __init__(self, stream, address, connections, notify_server):
        
        self.connections = connections
        self.stream = stream
        self.stream.set_close_callback(self._on_close)
        self.address = address                
        self.last_message_time = int(round(time.time() * 1000))
        self.fields = {}
        self.fields_num = 0
        self.notify_server = notify_server
        self.uid = None
        self.message_number = 0
        self.conn_id = uuid.uuid4()

        while self.conn_id in self.connections:
            self.conn_id = uuid.uuid4()
        
        self.connections[self.conn_id] = self

        logger.info('receive a new connection from {}, connections {} '.format(address, len(connections)))

        try: 
            self.stream.read_bytes(13, self._on_read_header, partial=True)        
        except BaseException as error:
            logger.info(error)
            self._on_error()

    def _on_read_header(self, data):
        logger.info('got a new message from %s - %s', self.address, data)

        try:
            self.last_message_time = int(round(time.time() * 1000))
            self.message_number = struct.unpack('>H',data[1:3])[0]      
            self.uid = data[3:11].decode('ascii')
            self.status = data[11]
            self.fields_num = data[12]

            logger.info('msg_num: {}, uid: {}, status: {}, fields_num: {}'.format(
                self.message_number,
                self.uid,
                self.status,
                self.fields_num))

            msg = [
                (SUCCESS).to_bytes(1, byteorder='big'),
                struct.pack('>H', self.message_number)
            ]
            self._calculate_response(msg)
            
            if self.fields_num == 0:
                self._read_more()
            
            self.stream.read_bytes(self.fields_num*12, self._on_read_fields, partial=True)  

        except BaseException as error:
            logger.info(error)
            self._on_error()       

    def _calculate_response(self, msg):
        msg_xor = b''.join(msg)
        bytes_arr = memoryview(msg_xor).cast('B')
        msg.append(struct.pack('>B', reduce(xor, msg_xor)))
        msg = b''.join(msg)
        self.response_msg = msg

    def _on_read_fields(self, data):
        logger.info('got a new fieldset from %s - %s', self.address, data)

        ends = [(x+1)*12 for x in range(self.fields_num)]
        starts = [x-12 for x in ends]
        for message_start, message_finish in zip_longest(starts, ends):
            mess = data[message_start:message_finish]
            logger.info('field data: %s', mess)
            name = mess[0:8].decode('ascii')
            value = struct.unpack('>L', mess[8:12])[0]
            self.fields[name] = value

        self.stream.read_bytes(1)
        self._read_more() 


    def _on_write_complete(self):
        self.response_msg = ''
        logging.info('write complete')
        self.notify_server.new_connection(self.conn_id)
        self._continue_reading()
    
    def _read_more(self):
        if self.response_msg == '':
            self._on_write_complete()

        self.stream.write(self.response_msg, self._on_write_complete)

    def _continue_reading(self):
        if not self.stream.reading():
            self.stream.read_bytes(13, self._on_read_header)
    
    def _on_close(self):
        logger.info('client quit %s - %s', self.address, self.uid)
        if self.conn_id != None:
            if self.conn_id in self.connections:
                del self.connections[self.conn_id]

    def _on_error(self):    
        msg = [
            (SUCCESS).to_bytes(1, byteorder='big'),
            struct.pack('>H', 0)
        ]
        msg_xor = b''.join(msg)
        bytes_arr = memoryview(msg_xor).cast('B')
        msg.append(struct.pack('>B', reduce(xor, msg_xor)))
        msg = b''.join(msg)
        self.write(msg, self._on_error_complete)

    def _on_error_complete(self):
        if not self.stream.reading():
            self.stream.read_bytes(13, self._on_read_header)



class StatusServer(TCPServer):
    
    def __init__(self, ssl_options=None, **kwargs):
        logger.info('connection monitoring app started')
        TCPServer.__init__(self, ssl_options=ssl_options, **kwargs)


    def handle_stream(self, stream, address):
        try:
            Connection(stream, address, client_conns, self.notify_server)
        except StreamClosedError:
            pass


class Notification(object):
    def __init__(self, stream, address, client_connections, notify_connections):

        logger.info('receive a new notify connection from %s', address)
        self.state = 'AUTH'
        self.client_connections = client_connections
        self.notify_connections = notify_connections
        self.stream = stream
        self.address = address
        self.stream.set_close_callback(self._on_close)
        self.conn_id = uuid.uuid4()

        while self.conn_id in self.notify_connections:
            self.conn_id = uuid.uuid4()
        
        self.notify_connections[self.conn_id] = self


        current_time = int(round(time.time() * 1000))
        exit_lines = []
        logging.info(client_connections)
        for client_name, client_interface in client_connections.items():        
            exit_lines.append(
                b''.join([
                    ord("[").to_bytes(1, byteorder='big'),
                    client_interface.uid.encode('ascii'),
                    ord("]").to_bytes(1, byteorder='big'),
                    struct.pack('>H', client_interface.message_number),
                    ord("|").to_bytes(1, byteorder='big'),
                    (client_interface.status).to_bytes(1, byteorder='big'),
                    struct.pack('>Q', current_time - client_interface.last_message_time),
                    ord('\n').to_bytes(1, byteorder='big'),
                ]))
        logging.info('listing currently connected sockets %s', b''.join(exit_lines))
        self.stream.write(b''.join(exit_lines))        
    
    def _on_close(self):
        logger.info('notification client quit %s - %s', self.address, self.conn_id)
        if self.conn_id in self.notify_connections:
            del self.notify_connections[self.conn_id]

class NotifyServer(TCPServer):
    
    def __init__(self, ssl_options=None, **kwargs):
        logger.info('connection notification app started')
        TCPServer.__init__(self, ssl_options=ssl_options, **kwargs)


    def handle_stream(self, stream, address):

        try:
            Notification(stream, address, client_conns, notify_conns)
        except StreamClosedError:
            pass

    def new_connection(self, conn_id):
        response = []     

        conn = client_conns[conn_id]
                   
        for field_key, field_value in conn.fields.items():
            response.append(
                b''.join([
                    ord("[").to_bytes(1, byteorder='big'),
                    conn.uid.encode('ascii'),
                    ord("]").to_bytes(1, byteorder='big'),
                    field_key.encode('ascii'),
                    ord("|").to_bytes(1, byteorder='big'),
                    struct.pack('>L', field_value),
                    ord('\n').to_bytes(1, byteorder='big'),
                ]))

        response = b''.join(response) 
        
        logging.info('sending notifications %s', response)
        logging.info('client conns %s', client_conns)

        for client_name, client_interface in notify_conns.items():        
            client_interface.stream.write(response)  
        

def main(conns, notify_conns):

    server = StatusServer()
    server.listen(8888)

    notify_server = NotifyServer()
    notify_server.listen(8889)

    server.notify_server = notify_server
    IOLoop.instance().start()


client_conns = {}
notify_conns = {}

if __name__ == '__main__':
    main(client_conns, notify_conns)