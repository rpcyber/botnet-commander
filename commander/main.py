from commander.helpers.helper import load_conf
from commander.server.bot_commander import BotCommander


(HOST, PORT, LOG_LEVEL, LOG_DIR, LOG_NAME, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW, API_HOST, API_PORT, API_PREFIX,
 API_LOG_LEVEL) = load_conf()

bot_server = BotCommander(HOST, PORT, LOG_LEVEL, LOG_DIR, LOG_NAME, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW,
                          API_HOST, API_PORT, API_PREFIX, API_LOG_LEVEL)

if __name__ == "__main__":
    bot_server.run()
