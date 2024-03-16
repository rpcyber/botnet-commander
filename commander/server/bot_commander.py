import asyncio
import logging
from socket import socket, AF_INET, SOCK_STREAM

from commander.db.db import CommanderDatabase
from commander.helpers.helper import json_serialize, json_deserialize


class BotCommander:
    def __init__(self, host, port, base_path, offline_tout, cmd_tout, resp_wait_window):
        self.logger = logging.getLogger(__name__+"."+self.__class__.__name__)
        self.db = CommanderDatabase(base_path, resp_wait_window)
        self.uuids = {}
        self.host = host
        self.port = port
        self.cmd_tout = cmd_tout
        self.offline_tout = offline_tout
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.result_list = None

    def __get_target_list(self, entity, op_sys):
        if entity == "*":
            if op_sys:
                target_list = []
                for uid, d in self.uuids.items():
                    if d.get("os") == op_sys:
                        target_list.append(uid)
            else:
                target_list = list(self.uuids.keys())
        else:
            if entity not in self.uuids or (op_sys and self.uuids.get(entity).get("os") != op_sys):
                target_list = []
            else:
                target_list = [entity]
        return target_list

    async def __write_data_to_target_list(self, target_list, json_dict, index_offset):
        self.result_list = []
        for index, uuid in enumerate(target_list):
            json_dict["cmd_id"] = index + index_offset
            await asyncio.wait_for(self.__write_to_agent_socket(uuid, json_serialize(json_dict)), timeout=60)
        return self.result_list

    async def __write_to_agent_socket(self, uuid, payload):
        try:
            self.logger.debug(f'Sending payload {payload} to bot-agent {uuid}')
            self.uuids[uuid]["writer"].write(payload)
            self.result_list.append({uuid: "success"})
        except Exception as err:
            self.logger.error(f'Unexpected exception when writing stream {payload.decode("utf-8")} to bot-agent'
                              f' {self.uuids.get(uuid)} - {err}', exc_info=True)
            self.result_list.append({uuid: f"failed: {err}"})

    async def __read_line(self, reader, addr):
        try:
            buffer = await asyncio.wait_for(reader.readline(), timeout=self.offline_tout)
        except TimeoutError:
            self.logger.error(f"Timeout exceeded for bot-agent {addr}, no input stream received in the"
                              f"last 200 seconds, setting bot-agent to offline, closing connection", exc_info=True)
            return False
        except Exception as err:
            self.logger.error(f"Unexpected exception when reading input stream from bot-agent {addr}: {err},"
                              f" setting bot-agent to offline, closing connection", exc_info=True)
            return False
        return buffer

    async def __read_buffer(self, reader, addr):
        buffer = await self.__read_line(reader, addr)
        if not buffer:
            return False
        self.logger.debug(f"Incoming input stream {buffer} from bot-agent {addr}")
        buffering = True
        data_list = []
        while buffering:
            if b"\n" in buffer:
                (line, buffer) = buffer.split(b"\n", 1)
                data_list.append(line)
                return data_list
            else:
                self.logger.debug(f"Received {data_list} from bot-agent {addr} so far, waiting for more data")
                more_data = await self.__read_line(reader, addr)
                self.logger.debug(f"Received more data {more_data} from bot-agent {addr}")
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
                        self.logger.error(f"Processing input stream from bot-agent {addr}-{uuid} has failed. "
                                          f"Closing connection and setting agent to offline", exc_info=True)
                        writer.close()
                        del self.uuids[uuid]
                        return
            else:
                self.logger.error(f"EOF received reading input stream from bot-agent {addr}-{uuid}. Closing"
                                  f" connection and setting agent to offline", exc_info=True)
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
            self.logger.error(f"Json builder was not able to build {message}, unknown request: args: {args}",
                              exc_info=True)
            return False
        return d

    def __process_input_stream(self, json_item, addr, reader, writer, uuid_in=None):
        self.logger.debug(f"Deserializing {json_item} received from bot-agent {addr}")
        json_msg = json_deserialize(json_item, addr, uuid_in)
        if not json_msg:
            return False
        message = json_msg.get("message")
        match message:
            case "botHostInfo":
                uuid = json_msg.get("uuid")
                hostname = json_msg.get("hostname")
                op_sys = json_msg.get("os")
                if uuid in self.db.db_agents:
                    self.logger.info(f'Agent {addr} with UUID {uuid} already present in DB.')
                    self.uuids[uuid] = {"reader": reader, "writer": writer, "hostname": hostname, "os": op_sys,
                                        "addr": addr}
                    if hostname != self.db.db_agents[uuid].get("hostname") or addr[0] != self.db.db_agents[uuid].get("addr")[0]:
                        self.logger.info(f"Agent {uuid} has changed his hostname or IP. New values for "
                                         f"hostname and IP: {hostname}:{addr[0]}")
                        self.db.db_agents[uuid]["addr"] = addr
                        self.db.db_agents[uuid]["hostname"] = hostname
                        rows = self.db.update_agent_addr_and_hostname(hostname, addr, uuid)
                        self.logger.debug(f"Updated database hostname and address entries for agent {uuid}. Rows "
                                          f"affected after transaction: {rows}")
                    return uuid
                else:
                    self.uuids[uuid] = {"reader": reader, "writer": writer, "hostname": hostname, "os": op_sys, "addr": addr}
                    rows = self.db.add_agent(uuid, hostname, addr, op_sys)
                    self.db.db_agents[uuid] = {"reader": reader, "writer": writer, "hostname": hostname, "os": op_sys, "addr": addr}
                    self.logger.info(f"Successfully added agent {hostname}-{uuid} to DB")
                    self.logger.debug(f"Affected rows by adding agent {hostname}-{uuid} : {rows} row")
                    return uuid
            case "botHello":
                json_dict = self.__json_builder("botHelloReply")
                payload = json_serialize(json_dict)
                if payload:
                    try:
                        self.logger.debug(f"Sending botHelloReply to bot-agent {addr}-{uuid_in}")
                        writer.write(payload)
                    except Exception as err:
                        self.logger.error(f"Unexpected exception sending botHelloReply to bot-agent "
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
                self.logger.error(f"Processing of message received from bot-agent {addr} has failed, unknown"
                                  f" message: {message}, commander cannot interpret this. Closing connection ",
                                  exc_info=True)
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
                            self.logger.debug(f'Sending botHostInfoReply to bot-agent {addr}-{agent_uuid}')
                            writer.write(payload)
                        except Exception as err:
                            self.logger.error(f'Unexpected error when sending botHostInfoReply to bot-agent '
                                              f'{addr}-{agent_uuid}: {err}. Closing connection, set agent to offline.',
                                              exc_info=True)
                            return
                        return agent_uuid
                    else:
                        self.logger.error(f"Closing connection of bot-agent {addr}:{agent_uuid} as adding process"
                                          f" was not successfully completed. Closing connection, set agent to"
                                          f" offline", exc_info=True)
                        return
                else:
                    self.logger.error(f"Decoding of getHostInfoReply from peer {addr} has failed, failed to add"
                                      f"bot-agent, closing connection", exc_info=True)
                    return
        else:
            self.logger.info(f"Closing connection to peer {addr}")
            return

    async def __handle_agent(self, reader, writer):
        addr = writer.get_extra_info('peername')
        self.logger.info(f"Connection accepted from peer {addr}")
        agent_uuid = await self.__add_agent(reader, writer, addr)
        if not agent_uuid:
            writer.close()
            return
        asyncio.create_task(self.__communicate_with_agent(reader, writer, addr, agent_uuid))

    def __close_agent_connections(self):
        for uid in self.uuids:
            if self.uuids[uid].get("writer"):
                try:
                    self.logger.debug(f"Closing socket for agent with UUID: {uid} and setting agent offline.")
                    self.uuids[uid]["writer"].close()
                except Exception as err:
                    self.logger.error(f"Unexpected exception when closing socket for agent {uid}: {err}")

    async def shutdown(self, s, loop):
        self.logger.info(f"Received exit signal {s.name}...")
        self.logger.info("Closing all connections to agents")
        self.__close_agent_connections()
        tasks = [t for t in asyncio.all_tasks() if t is not
                 asyncio.current_task()]

        [task.cancel() for task in tasks]

        self.logger.info(f"Cancelling {len(tasks)} running tasks")
        await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()

    async def start_listener(self):
        bot_server = await asyncio.start_server(self.__handle_agent, self.host, self.port)

        addrs = ", ".join(str(self.sock.getsockname()) for self.sock in bot_server.sockets)
        self.logger.info(f"Server started listener on {addrs}")

        async with bot_server:
            await bot_server.serve_forever()

    def count_agents(self, status, op_sys):
        match status:
            case "online":
                count_by_os = {
                    False: len(self.uuids),
                    True: sum(1 for uuid in self.uuids.values() if uuid.get("os") == op_sys)
                }
            case "offline":
                count_by_os = {
                    False: self.db.count_agents() - len(self.uuids),
                    True: self.db.count_agents(op_sys) - sum(1 for uuid in self.uuids.values() if uuid.get("os") == op_sys)
                }
            case _:
                count_by_os = {
                    False: self.db.count_agents(),
                    True: self.db.count_agents(op_sys)
                }
        return count_by_os[bool(op_sys)]

    def list_agents(self, entity, status, op_sys):
        if status == "online":
            if entity == "*":
                resp_list = []
                for uid, d in self.uuids.items():
                    if not op_sys or d.get("os") == op_sys:
                        tmp = {"id": uid, "hostname": d.get("hostname"), "addr": d.get("addr"), "os": d.get("os")}
                        resp_list.append(tmp)
                return resp_list
            else:
                d = self.uuids.get(entity)
                if d and (not op_sys or d.get("os") == op_sys):
                    return {"id": entity, "hostname": d.get("hostname"), "addr": d.get("addr"), "os": d.get("os")}
                else:
                    return {}
        elif status == "offline":
            if entity == "*":
                tmp = self.db.list_agents()
                for d in tmp:
                    uid = d.get("id")
                    if uid in self.uuids:
                        tmp.remove(d)
                return tmp
            elif entity in self.uuids:
                return {}
            else:
                return self.db.list_agents(op_sys, entity)
        else:
            if entity != "*":
                return self.db.list_agents(op_sys, entity)
            else:
                return self.db.list_agents(op_sys)

    def history_agents(self, entity, status, op_sys):
        d = {"online": False, "offline": True, "": ""}
        reverse = d.get(status)
        if entity == "*":
            uid_list = list(self.uuids.keys())
            return self.db.agents_history(uid_list, reverse, op_sys)
        else:
            if status == "online" and entity not in self.uuids:
                return []
            elif status == "offline" and entity in self.uuids:
                return []
            else:
                return self.db.agent_history(entity, op_sys)

    async def send_command(self, entity, command, op_sys):
        target_list = self.__get_target_list(entity, op_sys)
        json_dict = self.__json_builder("exeCommand", command)
        index_offset = self.db.get_last_row_id() + 1
        self.db.add_agent_events(target_list, command, json_dict.get("command"))
        self.result_list = await self.__write_data_to_target_list(target_list, json_dict, index_offset)
        return self.result_list

    async def send_script(self, entity, script_path, script_type, op_sys):
        target_list = self.__get_target_list(entity, op_sys)
        with open(script_path, 'r') as fh:
            script_data = fh.read()
        json_dict = self.__json_builder("exeScript", script_data, script_type, script_path)
        index_offset = self.db.get_last_row_id() + 1
        self.db.add_agent_events(target_list, json_dict.get("message"), json_dict.get("script"))
        self.result_list = await self.__write_data_to_target_list(target_list, json_dict, index_offset)
        return self.result_list

    async def delete_agents(self, entity, op_sys):
        return self.db.delete_agents(entity, op_sys)

    async def get_timeout(self):
        return self.cmd_tout

    async def set_timeout(self, new_value):
        self.cmd_tout = new_value
        return {"timeout set": "success"}
