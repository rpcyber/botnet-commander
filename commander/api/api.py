import uvicorn
import asyncio
from fastapi import FastAPI


class CommanderApi:
    app = FastAPI()
    prefix = "/api/v1"

    def __init__(self, agents, db, logger):
        self.agents = agents
        self.db = db
        self.addr = "0.0.0.0"
        self.port = 8080
        self.log_level = "info"
        self.logger = logger

    @staticmethod
    @app.get(f'{prefix}/agents/count', status_code=200)
    async def agents_count():
        # self.logger.core.info("Endpoint accessed: /agents/count")
        # return len(self.agents)
        return "Yes"

    async def start_api(self):
        asyncio.get_running_loop().run_in_executor(None, func=self.run_api_server)

    def run_api_server(self):
        uvicorn.run(CommanderApi.app, host=self.addr, port=self.port, log_level=self.log_level)
