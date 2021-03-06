#encoding=utf-8
import socket
import struct
from time import sleep
from operator import xor
from functools import reduce
import select
import random 

HOST = '127.0.0.1'
PORT = 8888
PORT2 = 8889

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
FIELD_NAME2 = '~~~~~~~2'.encode('ascii') 
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

msg = b''.join(msg)

s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s3 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

write_sockets = [
    s1,
    s2,
    s3,
]



try:
    for s in write_sockets:
        s.connect((HOST, PORT))    
        s.setblocking(0)
        s.settimeout(random.randint(1, 10))
    

    # 1 байт - header (всегда 0x01)
    # 2 байта - номер сообщения в пределах данного подключения (беззнаковое целое)
    # 8 байт - идентификатор источника (ascii-строка)
    # 1 байт - статус источника, (беззнаковое целое), возможные занчения: 0x01 -- IDLE, 0x02 -- ACTIVE, 0x03 -- RECHARGE
    # 1 байт - numfields, количество полей с данными (беззнаковое целое)
    # Затем, в соответствии со значением поля numfields, идёт несколько пар полей следующего вида:
    # 8 байт - имя поля (ascii-строка)
    # 4 байта - значение поля (беззнаковое целое)
    # 1 байт - побайтовый XOR от сообщения

    msg = [
        (HEADER).to_bytes(1, byteorder='big'),          
        MESSAGE_NUM,        
        TEST_SOURCE_NAME,   
        (ACTIVE).to_bytes(1, byteorder='big'),         
        NUM_FIELDS,
        FIELD_NAME,
        FIELD_VALUE
        ]

    msg1 = b''.join(msg)
    bytes_arr = memoryview(msg1).cast('B')
    msg.append(struct.pack('>B', reduce(xor, msg1)))
    msg1 = b''.join(msg)
  
    msg = [
        (HEADER).to_bytes(1, byteorder='big'),          
        struct.pack('>H', 2),        
        TEST_SOURCE_NAME,   
        (ACTIVE).to_bytes(1, byteorder='big'),         
        struct.pack('>B', 2),
        FIELD_NAME,
        FIELD_VALUE,
        FIELD_NAME2,
        FIELD_VALUE,
    ]
    msg2 = b''.join(msg)
    bytes_arr = memoryview(msg2).cast('B')
    msg.append(struct.pack('>B', reduce(xor, msg2)))
    msg2 = b''.join(msg)

    for s in write_sockets:
        s.send(msg1)
        s.recv(4)
        s.send(msg2)
        s.recv(4)

    readable, writable, exceptional  = select.select(write_sockets, [], [], 10)

    while write_sockets:
        if readable:
            for s in readable:
                data = s.recv(4)
                if data != '':
                    print(data)


    # s.shutdown(5)
    print("Success connecting to ")
    print(HOST," on port: ",str(PORT))
except socket.error as e:
    print("Cannot connect to ")
    print(HOST," on port: ",str(PORT))
    print(e)
