import uvicorn
import asyncio
from fastapi import FastAPI


app = FastAPI()


class CommanderApi:

    def __init__(self, host, port, prefix, log_level, api_router):
        self.addr = host
        self.port = port
        self.prefix = prefix
        self.api_router = api_router
        self.log_level = log_level

    def __run_server(self):
        uvicorn.run(app, host=self.addr, port=self.port, log_level=self.log_level)

    async def start_api(self):
        app.include_router(self.api_router, prefix=self.prefix)
        asyncio.get_running_loop().run_in_executor(None, func=self.__run_server)

