from typing import Optional
from fastapi import APIRouter, HTTPException

from commander.pki.pki_init import pki_init
from commander.api.api import CommanderApi
from commander.server.bot_commander import BotCommander
from commander.helpers.commander_logger import (HOST, PORT, BASE_PATH, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW,
                                                API_HOST, API_PORT, API_PREFIX, API_LOG_LEVEL)

pki_init(BASE_PATH)
bot_server = BotCommander(HOST, PORT, BASE_PATH, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW)

router = APIRouter()


@router.get("/agents/count", status_code=200)
def count_agents(filter: str = None) -> int:
    response = {
        None: bot_server.count_connected_agents,
        "offline": bot_server.count_connected_agents,
        "online": bot_server.count_connected_agents
    }
    if response.get(filter):
        return response.get(filter)()
    raise HTTPException(status_code=400, detail="Bad filter. Valid filters: ?filter=online, ?filter=offline")


api = CommanderApi(API_HOST, API_PORT, API_PREFIX, API_LOG_LEVEL, BASE_PATH, router)
