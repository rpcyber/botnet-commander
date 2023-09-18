import sys
import signal
import asyncio
from commander.api.api import CommanderApi
from commander.helpers.logger import Logger
from commander.db.db import CommanderDatabase
from socket import socket, AF_INET, SOCK_STREAM
from commander.helpers.helper import json_serialize, json_deserialize, load_conf


class BotCommander:
    def __init__(self, host, port, offline_tout, cmd_tout, resp_wait_window, api_host, api_port, api_prefix,
                 api_server_log_level):
        self.db = CommanderDatabase(resp_wait_window, logger)
        self.uuids = self.db.get_existent_agents()
        self.host = host
        self.port = port
        self.cmd_tout = cmd_tout
        self.offline_tout = offline_tout
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.api = CommanderApi(api_host, api_port, api_prefix, api_server_log_level, self.uuids, self.db, logger)
        self.main()

    def _get_target_list(self, cmd_filter):
        active_agents = [uid for uid in self.uuids if self.uuids[uid].get("writer")]
        if cmd_filter:
            target_list = []
            for agent_id in active_agents:
                if self.uuids[agent_id].get("os") == cmd_filter:
                    target_list.append(agent_id)
            return target_list
        return active_agents

    async def __schedule_command(self, command, cmd_filter, *args):
        self.target_list = self._get_target_list(cmd_filter)
        json_dict = self.__json_builder(command, *args)
        index_offset = self.db.get_last_row_id() + 1
        self.db.add_agent_events(self.target_list, command, json_dict.get("command"))
        self.success_list = []
        for index, uuid in enumerate(self.target_list):
            json_dict["cmd_id"] = index + index_offset
            await asyncio.wait_for(self.__send_cmd_to_bot_agent(uuid, json_serialize(json_dict)), timeout=60)

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
                        writer.close()
                        del self.uuids[uuid]
                        return
            else:
                logger.core.error(f"EOF received reading input stream from bot-agent {addr}-{uuid}. Closing connection "
                                  f"and setting agent to offline", exc_info=True)
                writer.close()
                del self.uuids[uuid]
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
        return d

    def __process_input_stream(self, json_item, addr, reader, writer, uuid_in=None):
        logger.core.debug(f"Deserializing {json_item} received from bot-agent {addr}")
        json_msg = json_deserialize(json_item, addr, uuid_in)
        if not json_msg:
            return False
        message = json_msg.get("message")
        match message:
            case "botHostInfo":
                uuid = json_msg.get("uuid")
                hostname = json_msg.get("hostname")
                op_sys = json_msg.get("os")
                if uuid in self.uuids:
                    logger.core.info(f'Agent {addr} with UUID {uuid} already present in DB.')
                    self.uuids[uuid]["reader"] = reader
                    self.uuids[uuid]["writer"] = writer
                    if hostname != self.uuids[uuid].get("hostname") or addr != self.uuids[uuid].get("addr"):
                        logger.core.info(f'Agent {uuid} has changed his hostname or address. New values for hostname '
                                         f'and address: {hostname}:{addr}')
                        self.uuids[uuid]["addr"] = addr
                        self.uuids[uuid]["hostname"] = hostname
                        rows = self.db.update_agent_addr_and_hostname(hostname, addr, uuid)
                        logger.core.debug(f'Updated database hostname and address entries for agent {uuid}. Rows '
                                          f'affected after transaction: {rows}')
                    return uuid
                else:
                    self.uuids[uuid] = {"reader": reader, "writer": writer, "hostname": hostname, "os": op_sys, "addr": addr}
                    rows = self.db.add_agent(uuid, hostname, addr, op_sys)
                    logger.core.info(f"Successfully added agent {hostname}-{uuid} to DB")
                    logger.core.debug(f"Affected rows by adding agent {hostname}-{uuid} : {rows} row")
                    return uuid
            case "botHello":
                json_dict = self.__json_builder("botHelloReply")
                payload = json_serialize(json_dict)
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
                cmd_id = json_msg.get("cmd_id")
                result = json_msg.get("result")
                exit_code = json_msg.get("exit_code")
                self.db.bulk_response.append((result, exit_code, cmd_id))
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
                    json_dict = self.__json_builder("botHostInfoReply")
                    payload = json_serialize(json_dict)
                    if payload:
                        try:
                            logger.core.debug(f'Sending botHostInfoReply to bot-agent {addr}-{agent_uuid}')
                            writer.write(payload)
                        except Exception as err:
                            logger.core.error(f'Unexpected error when sending botHostInfoReply to bot-agent '
                                              f'{addr}-{agent_uuid}: {err}. Closing connection, set agent to offline.',
                                              exc_info=True)
                            return
                        return agent_uuid
                    else:
                        logger.core.error(f"Closing connection of bot-agent {addr}:{agent_uuid} as adding process was"
                                          f" not successfully completed. Closing connection, set agent to offline",
                                          exc_info=True)
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
            if self.uuids[uid].get("writer"):
                try:
                    logger.core.debug(f"Closing socket for agent with UUID: {uid} and setting agent offline.")
                    self.uuids[uid]["writer"].close()
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
            self.db.check_pending_task = loop.create_task(self.db.check_if_pending())
            loop.create_task(self.api.start_api())
            loop.create_task(self.__server_run())
            loop.run_forever()
        finally:
            loop.close()
            logger.core.info("Successfully shutdown Commander.")
            sys.exit()


if __name__ == "__main__":
    (HOST, PORT, LOG_LEVEL, LOG_DIR, LOG_NAME, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW, API_HOST, API_PORT, API_PREFIX,
     API_LOG_LEVEL) = load_conf()
    logger = Logger(LOG_LEVEL, LOG_DIR, LOG_NAME)
    srv = BotCommander(HOST, PORT, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW, API_HOST, API_PORT, API_PREFIX, API_LOG_LEVEL)
