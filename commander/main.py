import signal
import asyncio

from fastapi import Depends, APIRouter

from commander.api.api import CommanderApi
from commander.helpers.helper import load_conf
from commander.server.bot_commander import BotCommander


(HOST, PORT, LOG_LEVEL, LOG_DIR, LOG_NAME, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW, API_HOST, API_PORT, API_PREFIX,
 API_LOG_LEVEL) = load_conf()
bot_server = BotCommander(HOST, PORT, LOG_LEVEL, LOG_DIR, LOG_NAME, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW)
router = APIRouter()


@router.get("/agents/count")
def count_agents() -> int:
    return bot_server.count_connected_agents()


api = CommanderApi(API_HOST, API_PORT, API_PREFIX, API_LOG_LEVEL, router)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda sig=s: asyncio.create_task(bot_server.shutdown(s, loop)))
    try:
        bot_server.db.check_pending_task = loop.create_task(bot_server.db.check_if_pending())
        loop.create_task(bot_server.start_listener())
        loop.create_task(api.start_api())
        loop.run_forever()
    finally:
        loop.close()
        bot_server.logger.core.info("Successfully shutdown Commander.")
