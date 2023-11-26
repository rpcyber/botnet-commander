from typing import Optional
from fastapi import Depends, APIRouter, HTTPException, Query

from commander.helpers.api_messages import INVALID_STATUS, INVALID_OS, INVALID_ENTITY
from commander.helpers.helper import is_uuid
from commander.pki.pki_init import pki_init
from commander.api.api import CommanderApi
from commander.server.bot_commander import BotCommander
from commander.helpers.commander_logger import (HOST, PORT, BASE_PATH, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW,
                                                API_HOST, API_PORT, API_PREFIX, API_LOG_LEVEL)

pki_init(BASE_PATH)
bot_server = BotCommander(HOST, PORT, BASE_PATH, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW)

router = APIRouter()


def validate_filter(status, os):
    if status and status not in ("online", "offline"):
        raise HTTPException(status_code=400, detail=INVALID_STATUS)
    if os and os not in ("Windows", "Linux"):
        raise HTTPException(status_code=400, detail=INVALID_OS)


def validate_entity(entity):
    if entity == "*" or is_uuid(entity):
        pass
    else:
        raise HTTPException(status_code=400, detail=INVALID_ENTITY)


@router.get("/agents/count", status_code=200)
def count_agents(status: Optional[str] = "", os: Optional[str] = ""):
    validate_filter(status, os)
    return bot_server.count_agents(status, os)


@router.get("/agents/{entity}/list", status_code=200)
def list_agents(entity: str, status: Optional[str] = "", os: Optional[str] = ""):
    validate_filter(status, os)
    validate_entity(entity)
    return bot_server.list_agents(entity, status, os)


@router.get("/agents/{entity}/history", status_code=200)
def history_agents(entity: str, status: Optional[str] = "", os: Optional[str] = ""):
    validate_filter(status, os)
    validate_entity(entity)
    return bot_server.history_agents(entity, status, os)


api = CommanderApi(API_HOST, API_PORT, API_PREFIX, API_LOG_LEVEL, BASE_PATH, router)
