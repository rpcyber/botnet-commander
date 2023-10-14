import os
import sys
import uuid
import logging
import datetime

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes, serialization


logger = logging.getLogger(__name__)


def pki_init(base_path):
    if not os.access(base_path, os.W_OK | os.X_OK):
        logger.error(f"Base folder: {base_path} does not exist or Commander doesn't have permissions for it. Please "
                     f"ensure that Commander has write and execute access to this folder and folder exists.")
        sys.exit(9)
    pki_path = f"{base_path}/pki"
    ca_fn = "commander-ca.pem"
    ca_key_fn = "commander-key.pem"
    os.mkdir(pki_path)
    if not os.path.isfile(f"{pki_path}/{ca_fn}") or not os.path.isfile(f"{pki_path}/{ca_key_fn}"):
        logger.info(f"CA files are not present in {pki_path}")
        generate_ca(pki_path, ca_fn, ca_key_fn)
    gen_api_certs(pki_path, ca_fn, ca_key_fn)


def gen_api_certs(pki_path, ca_fn, ca_key_fn):
    pass


def generate_ca(pki_path, ca_fn, ca_key_fn):
    logger.info("Generating Commander CA private key")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    builder = x509.CertificateBuilder()
    builder = builder.subject_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u'Commander CA'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u'Bot-Commander'),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, u'Commander'),
    ]))
    builder = builder.issuer_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u'Commander CA'),
    ]))
    builder = builder.not_valid_before(datetime.datetime.today())
    builder = builder.not_valid_after(datetime.datetime(2024, 1, 1))
    builder = builder.serial_number(int(uuid.uuid4()))
    builder = builder.public_key(public_key)
    builder = builder.add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True,
    )
    logger.info("Generating Commander CA certificate")
    certificate = builder.sign(
        private_key=private_key, algorithm=hashes.SHA256(),
        backend=default_backend()
    )

    with open(f"{pki_path}/{ca_fn}", "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(b"commander")
        ))

    with open(f"{pki_path}/{ca_key_fn}", "wb") as f:
        f.write(certificate.public_bytes(
            encoding=serialization.Encoding.PEM,
        ))
