import signal
import asyncio
from commander.api import routes


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(
            s, lambda sig=s: asyncio.create_task(routes.bot_server.shutdown(s, loop)))
    try:
        routes.bot_server.db.check_pending_task = loop.create_task(routes.bot_server.db.check_if_pending())
        loop.create_task(routes.bot_server.start_listener())
        loop.create_task(routes.api.start_api())
        loop.run_forever()
    finally:
        loop.close()
        routes.bot_server.logger.core.info("Successfully shutdown Commander.")
