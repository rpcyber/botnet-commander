import uvicorn
import asyncio
import logging
from fastapi import FastAPI


app = FastAPI()


class CommanderApi:

    def __init__(self, host, port, prefix, uvicorn_log_level, base_path, api_router):
        self.addr = host
        self.port = port
        self.prefix = prefix
        self.pki_path = f"{base_path}/pki"
        self.api_router = api_router
        self.api_key_fp = f"{self.pki_path}/api-key.pem"
        self.api_cert_fp = f"{self.pki_path}/api-cert.pem"
        self.api_log_level = uvicorn_log_level
        self.logger = logging.getLogger(__name__+"."+self.__class__.__name__)

    def __run_server(self):
        uvicorn.run(app, host=self.addr, port=self.port, log_level=self.api_log_level, ssl_certfile=self.api_cert_fp,
                    ssl_keyfile=self.api_key_fp, ssl_keyfile_password="commander-api")

    async def start_api(self):
        app.include_router(self.api_router, prefix=self.prefix)
        asyncio.get_running_loop().run_in_executor(None, func=self.__run_server)
