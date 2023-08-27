import uvicorn
from fastapi import FastAPI


class CommanderApi:
    app = FastAPI()
    prefix = "/api/v1"

    def __init__(self, agents, db):
        self.agents = agents
        self.db = db

    @app.get(f'{prefix}/agents/count')
    async def agents_count(self):
        return len(self.agents), 200

    @staticmethod
    def start_api():
        uvicorn.run(CommanderApi.app, host="0.0.0.0", port=8080, log_level='debug')
