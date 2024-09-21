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
    pki_path = f"{base_path}/pki"
    if not os.access(base_path, os.W_OK | os.X_OK):
        logger.error(f"Commander doesn't have permissions for {base_path}. Please ensure that Commander has write "
                     f"and execute permissions to this folder.")
        sys.exit(9)
    if not os.path.isdir(pki_path):
        os.mkdir(pki_path)
    ca_fn = "commander-ca.pem"
    ca_key_fn = "commander-key.pem"
    if not os.path.isfile(f"{pki_path}/{ca_fn}") or not os.path.isfile(f"{pki_path}/{ca_key_fn}"):
        logger.info(f"CA files are not present in {pki_path}")
        generate_ca(pki_path, ca_fn, ca_key_fn)
    gen_api_certs(pki_path, ca_fn, ca_key_fn)
    generate_server_certs(pki_path, ca_fn, ca_key_fn)


def gen_api_certs(pki_path, ca_fn, ca_key_fn):
    with open(f"{pki_path}/{ca_key_fn}", 'rb') as f:
        pem_data = f.read()
        ca_key = serialization.load_pem_private_key(pem_data, password=b"commander")

    with open(f"{pki_path}/{ca_fn}", 'rb') as f:
        pem_data = f.read()
        ca = x509.load_pem_x509_certificate(pem_data)

    cert_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    logger.info("Generated Commander API key")
    new_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"HQ"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Hackerland"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Bot-Commander"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, u"Commander API"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        new_subject
    ).issuer_name(
        ca.issuer
    ).public_key(
        cert_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=30)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
        critical=False,
    ).sign(ca_key, hashes.SHA256(), default_backend())

    logger.info("Generated Commander API certificate")
    with open(f"{pki_path}/api-cert.pem", 'wb') as f:
        f.write(cert.public_bytes(encoding=serialization.Encoding.PEM))

    with open(f"{pki_path}/api-key.pem", 'wb') as f:
        f.write(cert_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(b"commander-api")
        ))


def generate_server_certs(pki_path, ca_fn, ca_key_fn):
    with open(f"{pki_path}/{ca_key_fn}", 'rb') as f:
        pem_data = f.read()
        ca_key = serialization.load_pem_private_key(pem_data, password=b"commander")

    with open(f"{pki_path}/{ca_fn}", 'rb') as f:
        pem_data = f.read()
        ca = x509.load_pem_x509_certificate(pem_data)

    cert_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    logger.info("Generated Commander Server key")
    new_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"HQ"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Hackerland"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Bot-Commander"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, u"Commander Server"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        new_subject
    ).issuer_name(
        ca.issuer
    ).public_key(
        cert_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=30)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
        critical=False,
    ).sign(ca_key, hashes.SHA256(), default_backend())

    logger.info("Generated Commander Server certificate")
    
    with open(f"{pki_path}/server-cert.pem", 'wb') as f:
        f.write(cert.public_bytes(encoding=serialization.Encoding.PEM))

    with open(f"{pki_path}/server-key.pem", 'wb') as f:
        f.write(cert_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(b"commander-server")
        ))


def generate_ca(pki_path, ca_fn, ca_key_fn):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    logger.info("Generated Commander CA private key")
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
    builder = builder.not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=90))
    builder = builder.serial_number(int(uuid.uuid4()))
    builder = builder.public_key(public_key)
    builder = builder.add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True,
    )
    certificate = builder.sign(
        private_key=private_key, algorithm=hashes.SHA256(),
        backend=default_backend()
    )
    logger.info("Generated Commander CA certificate")

    with open(f"{pki_path}/{ca_key_fn}", "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(b"commander")
        ))

    with open(f"{pki_path}/{ca_fn}", "wb") as f:
        f.write(certificate.public_bytes(encoding=serialization.Encoding.PEM))
