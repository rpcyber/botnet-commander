from fastapi import APIRouter

from commander.api.api import CommanderApi
from commander.server.bot_commander import BotCommander
from commander.helpers.commander_logger import (HOST, PORT, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW, API_HOST,
                                                API_PORT, API_PREFIX, API_LOG_LEVEL, PKI_PATH)


bot_server = BotCommander(HOST, PORT, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW)

router = APIRouter()


@router.get("/agents/count")
def count_agents() -> int:
    return bot_server.count_connected_agents()


api = CommanderApi(API_HOST, API_PORT, API_PREFIX, API_LOG_LEVEL, PKI_PATH, router)
