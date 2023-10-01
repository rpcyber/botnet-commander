import os
import sys
import signal
import uvicorn
import asyncio
import logging
from fastapi import FastAPI
from cryptography import x509


app = FastAPI()


class CommanderApi:

    def __init__(self, host, port, prefix, uvicorn_log_level, pki_path, api_router):
        self.addr = host
        self.port = port
        self.prefix = prefix
        self.pki_path = pki_path
        self.api_router = api_router
        self.api_key = "api-key.pem"
        self.api_cert = "api-cert.pem"
        self.api_log_level = uvicorn_log_level
        self.logger = logging.getLogger(__name__+"."+self.__class__.__name__)

    def __run_server(self):
        self.__api_certs_check()
        uvicorn.run(app, host=self.addr, port=self.port, log_level=self.api_log_level, ssl_certfile="", ssl_keyfile="")

    def __api_certs_check(self):
        api_cert_path = os.path.join(self.pki_path, self.api_cert)
        api_key_path = os.path.join(self.pki_path, self.api_key)
        if not os.path.isfile(api_cert_path) or not os.path.isfile(api_key_path):
            self.logger.error(f"Certificate files {self.api_key} and {self.api_cert} were not found in "
                              f"{self.pki_path}. Please ensure that you have these files in th pki path which can"
                              f" be configured in commander.ini config file.")
            os.kill(os.getpid(), signal.SIGINT)
            sys.exit()

    def __api_certs_generate(self):
        pass

    async def start_api(self):
        app.include_router(self.api_router, prefix=self.prefix)
        asyncio.get_running_loop().run_in_executor(None, func=self.__run_server)

