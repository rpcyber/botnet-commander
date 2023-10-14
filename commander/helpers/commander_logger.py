from os import path
import logging.handlers
from commander.helpers.helper import load_conf


(HOST, PORT, LOG_LEVEL, BASE_PATH, LOG_NAME, OFFLINE_TOUT, CMD_TOUT, RESP_WAIT_WINDOW, API_HOST, API_PORT, API_PREFIX,
 API_LOG_LEVEL) = load_conf()

formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(name)s:: - %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
handlers = [
    logging.handlers.RotatingFileHandler(f"{BASE_PATH}/{LOG_NAME}", encoding="utf8", maxBytes=100000, backupCount=1),
    logging.StreamHandler()
]
root_logger = logging.getLogger()
root_logger.setLevel(LOG_LEVEL)
for h in handlers:
    h.setFormatter(formatter)
    h.setLevel(logging.DEBUG)
    root_logger.addHandler(h)
