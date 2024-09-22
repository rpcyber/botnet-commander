╭━━╮╱╱╱╭╮╱╱╱╱╱╱╭╮╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╭╮
┃╭╮┃╱╱╭╯╰╮╱╱╱╱╭╯╰╮╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱┃┃
┃╰╯╰┳━┻╮╭╋━╮╭━┻╮╭╯╭━━┳━━┳╮╭┳╮╭┳━━┳━╮╭━╯┣━━┳━╮
┃╭━╮┃╭╮┃┃┃╭╮┫┃━┫┃╱┃╭━┫╭╮┃╰╯┃╰╯┃╭╮┃╭╮┫╭╮┃┃━┫╭╯
┃╰━╯┃╰╯┃╰┫┃┃┃┃━┫╰╮┃╰━┫╰╯┃┃┃┃┃┃┃╭╮┃┃┃┃╰╯┃┃━┫┃
╰━━━┻━━┻━┻╯╰┻━━┻━╯╰━━┻━━┻┻┻┻┻┻┻╯╰┻╯╰┻━━┻━━┻╯

## Overview
AsyncIO implementation of a remote administration server and client. It uses a stateless permanent TLS connection for communication and client stands by and regularly sends a hello message acting as a keep-alive for the OS to keep connection.

It uses a simple JSON protocol for communication and the server is controled via a simple API.

### NOTE: Only compatible with python3.10 or higher

## What it can do
The following features are available:
    
    - view info about and send commands to connected agents
    - depending on agent type (Linux/Windows), commands can be:
        - cmd/powershell/bash 
        - powershell/python/bash scripts
    - others WIP

## How to run using python3 interpreter
### Start bot-agent and commander
```bash
sudo apt-get install -y python3 pip
git clone https://github.com/rpcyber/botnet-commander
pip install -r requirements.txt
cd bot-agent
python3 bot-agent.py &
cd ../commander
python3 main.py &
```

### Run multiple agents using docker
Before building the image ensure to edit the bot-agent.ini file accordingly

Build docker image using dockerfile from bot-agent directory
```bash
cd bot-agent
sudo docker build -t bot-agent .
```
Start 100 agents
```bash
sudo ./manage_bots.sh start 1 100
```