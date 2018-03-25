#encoding=utf-8
import socket
import struct
from time import sleep
import select


HOST = '127.0.0.1'
PORT = 8889


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


try:
    s.connect((HOST, PORT))
    s.setblocking(0)    
    while True:
        ready = select.select([s], [], [], 1000)
        if ready[0]:
            data = s.recv(4096)
            print(data)

    # s.shutdown(5)
    print("Success connecting to ")
    print(HOST," on port: ",str(PORT))
except socket.error as e:
    print("Cannot connect to ")
    print(HOST," on port: ",str(PORT))
    print(e)
