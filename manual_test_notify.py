#encoding=utf-8
import socket
import struct
from time import sleep
import select
import logging
from logging.handlers import RotatingFileHandler


LOG_FILENAME = 'test.log'
fileHandler = RotatingFileHandler(
    LOG_FILENAME, maxBytes=1024*1024*1024,
    backupCount=5, encoding='utf-8')
fileHandler.setLevel(logging.DEBUG)
filefmt = '%(asctime)s [%(filename)s:%(lineno)d] %(message)s'
fileFormatter = logging.Formatter(filefmt)
fileHandler.setFormatter(fileFormatter)

logger = logging.getLogger(__name__)
logger.addHandler(fileHandler)
logger.setLevel(logging.INFO)


HOST = '127.0.0.1'
PORT = 8889


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


try:
    s.connect((HOST, PORT))
    s.setblocking(0)    

    while s:
        ready = select.select([s], [], [], 1000)
        if ready[0]:
            data = s.recv(4096)
            logger.info(data)
            print(data)

    # s.shutdown(5)
    print("Success connecting to ")
    print(HOST," on port: ",str(PORT))
except socket.error as e:
    print("Cannot connect to ")
    print(HOST," on port: ",str(PORT))
    print(e)
