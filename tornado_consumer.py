
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

def main():
    io_loop = IOLoop.instance()
    pc = PikaClient(io_loop)

    server = NotifyServer()
    server.pc = pc
    server.pc.connect()
    server.listen(8889)
    io_loop.start()

if __name__ == '__main__':
    main()