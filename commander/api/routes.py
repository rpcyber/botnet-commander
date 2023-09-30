from fastapi import Depends, APIRouter

from commander.api.api import CommanderApi
from commander.server.bot_commander import BotCommander
from commander.helpers.helper import load_conf


(HOST, PORT, LOG_LEVEL, LOG_DIR, LOG_NAME, OFFLINE_TOUT, CMD_TOUT, PKI_PATH, RESP_WAIT_WINDOW, API_HOST, API_PORT,
 API_PREFIX, API_LOG_LEVEL) = load_conf()

bot_server = BotCommander(HOST, PORT, LOG_LEVEL, LOG_DIR, LOG_NAME, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW)

router = APIRouter()


@router.get("/agents/count")
def count_agents() -> int:
    return bot_server.count_connected_agents()


api = CommanderApi(API_HOST, API_PORT, API_PREFIX, API_LOG_LEVEL, PKI_PATH, router)
