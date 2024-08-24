import logging
import signal
import asyncio

from commander import app
import commander.helpers.commander_logger


logger = logging.getLogger(__name__)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda sig=s: asyncio.create_task(app.bot_server.shutdown(s, loop)))
    try:
        app.bot_server.db.check_pending_task = loop.create_task(app.bot_server.db.check_if_pending())
        loop.create_task(app.bot_server.start_listener())
        loop.create_task(app.api.start_api())
        loop.run_forever()
    finally:
        loop.close()
        app.bot_server.logger.info("Successfully shutdown Commander.")
