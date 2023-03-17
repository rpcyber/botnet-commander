import os
import asyncio
import json
from pathlib import Path
import time
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
        asyncio.run(self.__run())

    async def __send_instructions(self, reader, writer):
        message = "Hello"
        addr = writer.get_extra_info('peername')
        logger.core.debug(f"Sending data {message} to peer {addr}")
        writer.write(message.encode("utf-8"))

        data = await reader.read(self.conn_rcv)
        message = data.decode("utf-8")
        logger.core.debug(f"Received {message} from {addr}")

        writer.close()

    async def __identify_agent(self, reader, writer):
        addr = writer.get_extra_info('peername')
        logger.core.info(f"Connection accepted from peer {addr}")
        hostname = await self.__get_hostname(reader, writer, addr)
        try:
            data = await reader.read(self.conn_rcv)
        except Exception as err:
            logger.core.error(f"Unexpected exception when reading agent UUID from peer {hostname}: {err},"
                              f" closing connection")
            writer.close()
            return
        if not data:
            logger.core.error(f"Received EOF or empty response from peer {hostname}-{addr} when reading UUID")
            writer.close()
            return
        uuid = data.decode("uft-8")
        logger.core.debug(f"Received UUID {uuid} from peer {hostname}-{addr}")
        if uuid in self.uuids:
            logger.core.debug(f"Agent {self.uuids[uuid]} with UUID {uuid} already present in DB")
        else:
            online = True
            self.uuids[uuid] = (hostname, online)
            logger.core.debug(f"Successfully added agent {hostname}-{uuid} to DB")
        try:
            writer.write(b"getUUIDReply")
        except Exception as err:
            logger.core.error(f"Unexpected exception when sending getUUIDReply to {hostname}: {err},"
                              f" closing connection")
            writer.close()
            return

    @staticmethod
    def __get_uuid_payload():
        return "getUUID".encode("utf-8")

    async def __get_hostname(self, reader, writer, addr):
        try:
            data = await reader.read(self.conn_rcv)
        except Exception as err:
            logger.core.error(f"Unexpected exception when reading hostname from peer {addr}: {err},"
                              f" closing connection")
            return
        if not data:
            logger.core.error(f"Received EOF or empty response from peer {addr} when reading hostname")
            writer.close()
            return
        hostname = data.decode("utf-8")
        logger.core.debug(f"Received hostname {hostname} from peer {addr}")
        try:
            writer.write(b"getHostnameReply")
        except Exception as err:
            logger.core.error(f"Unexpected exception when sending getHostnameReply to {hostname}: {err},"
                              f" closing connection")
            writer.close()
            return
        return hostname

    async def __run(self):
        server = await asyncio.start_server(self.__identify_agent, self.host, self.port)

        addrs = ", ".join(str(self.sock.getsockname()) for self.sock in server.sockets)
        logger.core.info(f"Server started listener on {addrs}")

        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    HOST, PORT, LOG_LEVEL, LOG_DIR, LOG_NAME, CONN_BUFF = load_conf()
    logger = CoreLogger(LOG_LEVEL, LOG_DIR, LOG_NAME)
    srv = BotCommander(HOST, PORT, CONN_BUFF)
    logger.core.info("Botnet-Commander exited")
