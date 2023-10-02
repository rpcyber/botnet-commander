import os
import sys
import uvicorn
import asyncio
import logging
from cryptography import x509
from fastapi import FastAPI
from signal import SIGTERM


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
        self.__check_certs_exist()
        uvicorn.run(app, host=self.addr, port=self.port, log_level=self.api_log_level, ssl_certfile="", ssl_keyfile="")

    def __check_certs_exist(self):
        cert_path = os.path.join(self.pki_path, self.api_cert)
        key_path = os.path.join(self.pki_path, self.api_key)
        if os.path.isfile(cert_path) and os.path.isfile(key_path):
            self.logger.debug(f"Certificate files {self.api_key} and {self.api_cert} have been found in {self.pki_path}"
                              f". Attempting to load and check if issuer is the same CA used by Commander")
            self.__certs_check_issuer(cert_path, key_path)
        else:
            self.logger.debug(f"Certificate files have not been found in {self.pki_path}, attempting to create them")
            self.__certs_generate()

    def __certs_check_issuer(self, cert_path, key_path):
        for file in cert_path, key_path:
            try:
                fh = open(file, 'b')
                x509.load_pem_x509_certificate(fh.read())
            except ValueError:
                self.logger.error(f"Certificate file {file} is not a valid pem file or is malformed. Please ensure that"
                                  f"the pem certificate file is valid. You can remove them and Commander will generate"
                                  f" new ones at startup")
                os.kill(os.getpid(), SIGTERM)
                sys.exit()
            except Exception as err:
                self.logger.error(f"Unexpected exception occurred when attempting to check certificates issuer: {err}")
                os.kill(os.getpid(), SIGTERM)
                sys.exit()

    def __certs_generate(self):
        pass

    async def start_api(self):
        app.include_router(self.api_router, prefix=self.prefix)
        asyncio.get_running_loop().run_in_executor(None, func=self.__run_server)
