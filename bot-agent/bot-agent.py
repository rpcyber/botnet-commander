import os
import uuid
from subprocess import Popen
import json
from pathlib import Path
import time
from math import pow
import configparser
from socket import socket, AF_INET, SOCK_STREAM, gethostname


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
        idle_timeout = int(config_parser.get("CORE", "IDLE_TIMEOUT"))
        conn_buff = int((config_parser.get("CORE", "CONN_BUFF")))
        recv_tout = int((config_parser.get("CORE", "RECV_TIMEOUT")))
    except Exception as err:
        print("Error initializing CORE, bot agent not started because config file could not be loaded. Unexpected "
              "exception occurred: {}".format(err))
        exit(5)
    return host, port, max_reconn, conn_buff, idle_timeout, recv_tout


class BotAgent:
    def __init__(self, host, port, max_reconn, idle_timeout, conn_buff, recv_tout):
        self.host = host
        self.port = port
        self.hostname = gethostname()
        self.max_reconn = max_reconn
        self.idle = False
        self.recv_tout = recv_tout
        self.idle_tout = idle_timeout
        self.conn_buff = conn_buff
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.reconnect_count = 0
        self.__check_uuid()
        self.__self_identify()

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
            self.last_online = time.time()
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

    def __self_identify(self):
        self.__tcp_handshake()
        self.sock.settimeout(self.recv_tout)
        if self.__generic_send_receive(self.hostname, "hostname", "getHostnameReply") and \
                self.__generic_send_receive(self.uuid, "UUID", "getUUIDReply"):
            print("Identification process for bot-agent {}-{} is successful".format(self.hostname, self.uuid))
            self.__check_for_commands()
        else:
            self.__self_identify()

    def __generic_send_receive(self, payload, req, expected_resp):
        try:
            print("Sending {} from bot-agent {} to commander".format(req, self.hostname))
            self.sock.sendall(payload.encode("utf-8"))
        except Exception as err:
            print("Unexpected error occurred while sending {} of peer {} to commander: {}".format(req, self.hostname, err))
            return False
        try:
            data = self.sock.recv(self.conn_buff)
        except Exception as err:
            print("Unexpected error occurred while reading {} by peer {}: {}".format(expected_resp, self.hostname, err))
            return False
        if not data:
            print("Received EOF or empty response by peer {}-{} from commander instead of {}".
                  format(self.hostname, self.uuid, expected_resp))
            return False
        elif data.decode("utf-8") == expected_resp:
            print("Bot-agent {} received {} from commander".format(self.hostname, expected_resp))
        else:
            print("Unknown reply {} from commander sent to bot-agent {}. Expecting {}"
                  .format(data.decode("utf-8"), self.hostname, expected_resp))
            return False
        return True

    def __check_for_commands(self):
        while True:
            data = ""
            if time.time() - self.last_online > self.idle_tout:
                # Send hello to commander so that it knows this bot-agent is still online
                if self.__keep_alive():
                    continue
                else:
                    self.__self_identify()
            self.sock.settimeout(self.recv_tout)
            try:
                data = self.sock.recv(self.conn_buff)
            except TimeoutError:
                print("Bot-agent {} has not received any request from commander in the past {} seconds. Still waiting".
                      format(self.hostname, self.recv_tout))
            except Exception as err:
                print("Unexpected error on bot-agent {} when reading input stream from commander, error: {}".
                      format(self.hostname, err))
            if data:
                self.__process_command(data)

    def __keep_alive(self):
        try:
            self.sock.sendall(b"Hello")
        except Exception as err:
            print("Unexpected exception occurred for bot-agent {} when sending Hello to commander: {}".
                  format(self.hostname, err))
            return False
        try:
            data = self.sock.recv(self.conn_buff)
        except TimeoutError as err:
            print("Timeout occurred for bot-agent {} when reading HelloReply from commander: {}. Reconnecting".
                  format(self.hostname, err))
            return False
        if data:
            try:
                msg = data.decode("utf-8")
                if msg == "HelloReply":
                    self.last_online = time.time()
                    return True
                else:
                    print("Unexpected message content received by bot-agent {} from commander".
                          format(self.hostname))
                    return False
            except Exception as err:
                print("Unexpected error while decoding reply from commander for Hello sent by bot-agent {}: {}"
                      .format(self.hostname, err))
                return False
        else:
            print("Received EOF by bot-agent {} from commander. Reconnecting".format(self.hostname))
            return False

    def __identify_command(self, data):
        payload = ""

        self.sock.sendall(payload)
        self.last_online = time.time()


if __name__ == "__main__":
    HOST, PORT, MAX_RECONN, CONN_BUFF, IDLE_TIMEOUT, RECV_TOUT = load_conf()
    client = BotAgent(HOST, PORT, MAX_RECONN, IDLE_TIMEOUT, CONN_BUFF, RECV_TOUT)
