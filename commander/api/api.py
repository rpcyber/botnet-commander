import os
import uvicorn
import asyncio
from fastapi import FastAPI


app = FastAPI()


class CommanderApi:

    def __init__(self, host, port, prefix, log_level, pki_path, api_router):
        self.addr = host
        self.port = port
        self.prefix = prefix
        self.pki_path = pki_path
        self.log_level = log_level
        self.api_router = api_router
        self.api_cert = "api-cert.pem"
        self.api_key = "api-key.pem"

    def __run_server(self):
        uvicorn.run(app, host=self.addr, port=self.port, log_level=self.log_level)

    def __api_certs_gen(self):
        api_cert_path = os.path.join(self.pki_path, self.api_cert)
        api_key_path = os.path.join(self.pki_path, self.api_key)

    async def start_api(self):
        app.include_router(self.api_router, prefix=self.prefix)
        asyncio.get_running_loop().run_in_executor(None, func=self.__run_server)

