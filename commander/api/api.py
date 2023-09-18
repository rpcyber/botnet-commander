import uvicorn
import asyncio
from fastapi import FastAPI

from starlette.status import HTTP_200_OK


class CommanderApi:
    app = FastAPI()

    def __init__(self, host, port, prefix, log_level, agents, db, logger):
        self.agents = agents
        self.db = db
        self.addr = host
        self.port = port
        self.log_level = log_level
        self.logger = logger
        self.app.include_router(router, prefix=prefix)

    @staticmethod
    @app.get("/agents/count", status_code=HTTP_200_OK)
    async def agents_count():
        return len(CommanderApi.agents)

    async def start_api(self):
        asyncio.get_running_loop().run_in_executor(None, func=self.run_api_server)

    def run_api_server(self):
        uvicorn.run(CommanderApi.app, host=self.addr, port=self.port, log_level=self.log_level)
