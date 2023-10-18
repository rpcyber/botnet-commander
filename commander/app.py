from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from commander.helpers.api_messages import INVALID_STATUS, INVALID_OS
from commander.pki.pki_init import pki_init
from commander.api.api import CommanderApi
from commander.server.bot_commander import BotCommander
from commander.helpers.commander_logger import (HOST, PORT, BASE_PATH, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW,
                                                API_HOST, API_PORT, API_PREFIX, API_LOG_LEVEL)

pki_init(BASE_PATH)
bot_server = BotCommander(HOST, PORT, BASE_PATH, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW)

router = APIRouter()


@router.get("/agents/count", status_code=200)
def count_agents(status: Optional[str] = "", os: Optional[str] = ""):
    if status and status not in ("online", "offline"):
        raise HTTPException(status_code=400, detail=INVALID_STATUS)
    if os and os not in ("Windows", "Linux"):
        raise HTTPException(status_code=400, detail=INVALID_OS)
    return bot_server.count_agents(status, os)


api = CommanderApi(API_HOST, API_PORT, API_PREFIX, API_LOG_LEVEL, BASE_PATH, router)
