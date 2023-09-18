import uvicorn
import asyncio
from fastapi import FastAPI

from commander.api.routes import router as api_router


class CommanderApi:
    app = FastAPI()

    def __init__(self, host, port, prefix, log_level, logger):
        self.addr = host
        self.port = port
        self.log_level = log_level
        self.logger = logger
        self.app.include_router(api_router, prefix=prefix)

    async def start_api(self):
        asyncio.get_running_loop().run_in_executor(None, func=self.run_api_server)

    def run_api_server(self):
        uvicorn.run(CommanderApi.app, host=self.addr, port=self.port, log_level=self.log_level)
