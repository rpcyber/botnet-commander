from typing import Optional
from pydantic import BaseModel
from fastapi import Depends, APIRouter, HTTPException, Query

from commander.helpers.api_messages import INVALID_STATUS, INVALID_OS, INVALID_ENTITY, INVALID_TYPE, INVALID_PATH
from commander.helpers.helper import is_uuid, check_if_path_is_valid
from commander.pki.pki_init import pki_init
from commander.api.api import CommanderApi
from commander.server.bot_commander import BotCommander
from commander.helpers.commander_logger import (HOST, PORT, BASE_PATH, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW,
                                                API_HOST, API_PORT, API_PREFIX, API_LOG_LEVEL)

pki_init(BASE_PATH)
bot_server = BotCommander(HOST, PORT, BASE_PATH, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW)

router = APIRouter()


class Command(BaseModel):
    cmd: str


class Script(BaseModel):
    script_path: str
    script_type: str


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


def validate_type(s_type):
    if s_type not in ("sh", "powershell", "python"):
        raise HTTPException(status_code=400, detail=INVALID_TYPE)


def validate_path(s_path):
    if not check_if_path_is_valid(s_path):
        raise HTTPException(status_code=400, detail=INVALID_PATH)


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


@router.post("/agents/{entity}/cmd", status_code=200)
async def send_command(entity: str, command: Command, os: Optional[str] = ""):
    validate_filter("", os)
    validate_entity(entity)
    return await bot_server.send_command(entity, command.cmd, os)


@router.post("/agents/{entity}/script", status_code=200)
async def send_script(entity: str, script: Script, os: Optional[str] = ""):
    validate_filter("", os)
    validate_entity(entity)
    s_path = script.script_path
    s_type = script.script_type
    validate_type(s_type)
    validate_path(s_path)
    return await bot_server.send_script(entity, s_path, s_type, os)

api = CommanderApi(API_HOST, API_PORT, API_PREFIX, API_LOG_LEVEL, BASE_PATH, router)
