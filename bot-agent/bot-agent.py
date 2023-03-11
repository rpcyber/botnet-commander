import os
import uuid
import json
from pathlib import Path
import time
from math import pow
import configparser
from socket import socket, AF_INET, SOCK_STREAM


def load_conf():
    config_parser = configparser.ConfigParser()
    cwd_path = Path(__file__)
    root_dir = cwd_path.parent.absolute()
    try:
        config_path = os.path.join(root_dir, "cfg/bot-agent.ini")
        config_parser.read(config_path)
        host = config_parser.get("CORE", "HOST")
        port = int(config_parser.get("CORE", "PORT"))
        max_reconn = int(config_parser.get("CORE", "MAX_RECONN"))
        idle_time = int(config_parser.get("CORE", "IDLE_TIME"))
        nidle_time = int(config_parser.get("CORE", "NIDLE_TIME"))
        idle_timeout = int(config_parser.get("CORE", "IDLE_TIMEOUT"))
        conn_buff = int((config_parser.get("CORE", "CONN_BUFF")))
        recv_tout = int((config_parser.get("CORE", "RECV_TIMEOUT")))
    except Exception as err:
        print("Error initializing CORE, bot agent not started because config file could not be loaded. Unexpected "
              "exception occurred: {}".format(err))
        exit(5)
    return host, port, max_reconn, conn_buff, idle_time, nidle_time, idle_timeout, recv_tout


class BotAgent:
    def __init__(self, host, port, max_reconn, idle_time, nidle_time, idle_timeout, conn_buff, recv_tout):
        self.host = host
        self.port = port
        self.max_reconn = max_reconn
        self.idle = False
        self.last_online = time.time()
        self.recv_tout = recv_tout
        self.idle_t = idle_time
        self.nidle_t = nidle_time
        self.idle_tout = idle_timeout
        self.conn_buff = conn_buff
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.reconnect_count = 0
        self.__check_uuid()
        self.__run()

    def __check_uuid(self):
        self.uid_path = os.path.join("/opt/bot-agent/", ".bot-agent.id")
        if os.path.isfile(self.uid_path):
            with open(self.uid_path, 'r') as fh:
                self.uuid = fh.read()
        else:
            self.uuid = self.__gen_uuid()

    def __gen_uuid(self):
        new_uuid = str(uuid.uuid4())
        with open(self.uid_path, 'w') as fh:
            fh.write(new_uuid)
        return new_uuid

    def __tcp_handshake(self):
        try:
            self.sock.close()
            self.sock = socket(AF_INET, SOCK_STREAM)
            self.sock.connect((self.host, self.port))
        except Exception as err:
            print("Unexpected error occurred when connecting to commander: {}".format(err))
            self.sock.close()
            self.__reconnect()
        self.reconnect_count = 0

    def __reconnect(self):
        if self.reconnect_count < self.max_reconn:
            self.reconnect_count += 1
        time.sleep(pow(2, self.reconnect_count))
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.__tcp_handshake()

    def __tls_handshake(self):
        pass

    def __run(self):
        while True:
            data = ""
            self.__tcp_handshake()
            self.sock.settimeout(self.recv_tout)
            try:
                data = self.sock.recv(self.conn_buff)
            except Exception as err:
                print(f"Timeout exceeded while waiting for data from commander, error: {err}")
                self.__run()
            # Waiting time for checking if commander is sending data
            if time.time() - self.last_online > self.idle_tout:
                self.idle = True
            if self.idle:
                time.sleep(self.idle_t)
            else:
                time.sleep(self.nidle_t)
            if data:
                self.__process_command(data)

    def __process_command(self, data):
        self.sock.sendall(data)
        self.last_online = time.time()


if __name__ == "__main__":
    HOST, PORT, MAX_RECONN, CONN_BUFF, IDLE_T, NIDLE_T, IDLE_TIMEOUT, RECV_TOUT = load_conf()
    client = BotAgent(HOST, PORT, MAX_RECONN, IDLE_T, NIDLE_T, IDLE_TIMEOUT, CONN_BUFF, RECV_TOUT)
