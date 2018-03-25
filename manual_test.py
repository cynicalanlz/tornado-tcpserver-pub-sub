#encoding=utf-8
import socket
import struct
from time import sleep


HOST = '127.0.0.1'
PORT = 8888


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

msg = b''.join(msg)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)



try:
    s.connect((HOST, PORT))
    
    s.settimeout(100)

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

    msg = b''.join(msg)

    s.send(msg)
    q = s.recv(4)

    while True:
        s.recv(4)

    # s.shutdown(5)
    print("Success connecting to ")
    print(HOST," on port: ",str(PORT))
except socket.error as e:
    print("Cannot connect to ")
    print(HOST," on port: ",str(PORT))
    print(e)
