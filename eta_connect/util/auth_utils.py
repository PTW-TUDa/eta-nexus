from __future__ import annotations

import pathlib
import socket
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

import pytz
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

if TYPE_CHECKING:
    from collections.abc import Generator
    from tempfile import _TemporaryFileWrapper

    from eta_connect.util.type_annotations import Path, PrivateKey


class KeyCertPair(ABC):
    """KeyCertPair is a wrapper for an RSA private key file and a corresponding x509 certificate. Implementations
    provide a contextmanager "tempfiles", which provides access to the certificate files and the
    properties key and cert, which contain the RSA key and certificate information."""

    def __init__(self, key: PrivateKey, cert: x509.Certificate):
        self._key = key
        self._cert = cert

    @property
    def key(self) -> PrivateKey:
        """RSA private key for the certificate."""
        return self._key

    @property
    def cert(self) -> x509.Certificate:
        """x509 certificate information."""
        return self._cert

    @contextmanager
    @abstractmethod
    def tempfiles(self) -> Generator:
        """Accessor for temporary certificate files."""
        raise NotImplementedError

    @property
    @abstractmethod
    def key_path(self) -> str:
        """Path to the key file."""
        raise NotImplementedError

    @property
    @abstractmethod
    def cert_path(self) -> str:
        """Path to the certificate file."""
        raise NotImplementedError


class SelfsignedKeyCertPair(KeyCertPair):
    """Self signed key and certificate pair for use with the connections.

    :param common_name: Common name the certificate should be valid for.
    :param passphrase: Pass phrase for encryption of the private key.
    :param country: Country code for the certificate owner, for example "DE" or "US".
    :param province: Province name of the certificate owner. Empty by default.
    :param city: City name of the certificate owner. Empty by default.
    :param organization: Name of the certificate owner's organization. "OPC UA Client" by default.
    """

    def __init__(
        self,
        common_name: str,
        passphrase: str | None = None,
        country: str | None = None,
        province: str | None = None,
        city: str | None = None,
        organization: str | None = None,
    ) -> None:
        super().__init__(*self.generate_cert(common_name, country, province, city, organization))

        self._key_tempfile: _TemporaryFileWrapper[bytes] | None = None
        self._cert_tempfile: _TemporaryFileWrapper[bytes] | None = None

        self.passphrase = passphrase

    def generate_cert(
        self,
        common_name: str,
        country: str | None = None,
        province: str | None = None,
        city: str | None = None,
        organization: str | None = None,
    ) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
        """Generate a self signed key and certificate pair for use with the connections.

        :param common_name: Common name the certificate should be valid for.
        :param country: Alpha-2 country code for the certificate owner. Empty by default.
        :param province: Province name of the certificate owner. Empty by default.
        :param city: City name of the certificate owner. Empty by default.
        :param organization: Name of the certificate owner's organization. "OPC UA Client" by default.
        :return: Tuple of RSA private key and x509 certificate.
        """

        # Determine certificate subject and issuer from input values.
        subject_attributes = []

        if country is not None:
            subject_attributes.append(x509.NameAttribute(NameOID.COUNTRY_NAME, country))
        if province is not None:
            subject_attributes.append(x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, province))
        if city is not None:
            subject_attributes.append(x509.NameAttribute(NameOID.LOCALITY_NAME, city))
        if organization is None:
            organization = "OPC UA Client eta-connect"
        subject_attributes.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization))

        subject = issuer = x509.Name(subject_attributes)

        # Generate the private key
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(tz=pytz.utc))
            .not_valid_after(datetime.now(tz=pytz.utc) + timedelta(days=10))  # Certificate valid for 10 days
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.DNSName("localhost"), x509.DNSName(socket.gethostbyname(socket.gethostname()))]
                ),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )  # Sign certificate with our private key

        return key, cert

    def store_tempfile(self) -> tuple[str, str]:
        """Store the key and certificate as named temporary files. The function returns the names
        of the two files.

        :return: Tuple of name of the key file and name of the certificate file.
        """
        # store key
        if self.passphrase is not None:
            encryption: serialization.KeySerializationEncryption = serialization.BestAvailableEncryption(
                bytes(self.passphrase, "utf-8")
            )
        else:
            encryption = serialization.NoEncryption()

        with NamedTemporaryFile("w+b", delete=False, suffix=".pem") as key_tempfile:
            key_tempfile.write(
                self.key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=encryption,
                )
            )
            self._key_tempfile = key_tempfile
        # store cert
        with NamedTemporaryFile("w+b", delete=False, suffix=".pem") as cert_tempfile:
            cert_tempfile.write(self.cert.public_bytes(serialization.Encoding.PEM))
            self._cert_tempfile = cert_tempfile
        return self.key_path, self.cert_path

    @contextmanager
    def tempfiles(self) -> Generator:
        """Accessor for temporary certificate files."""
        try:
            self.store_tempfile()
            assert self._key_tempfile is not None
            assert self._cert_tempfile is not None

            self._key_tempfile.close()
            self._cert_tempfile.close()
            yield self
        finally:
            try:
                assert self._key_tempfile is not None
                pathlib.Path(self._key_tempfile.name).unlink()
            except BaseException:
                pass

            try:
                assert self._cert_tempfile is not None
                pathlib.Path(self._cert_tempfile.name).unlink()
            except BaseException:
                pass

    @property
    def key_path(self) -> str:
        """Path to the key file."""
        if self._key_tempfile is None:
            raise RuntimeError("Create the key file before trying to reference the filename")
        return self._key_tempfile.name

    @property
    def cert_path(self) -> str:
        """Path to the certificate file."""
        if self._cert_tempfile is None:
            raise RuntimeError("Create the certificate file before trying to reference the filename")
        return self._cert_tempfile.name


class PEMKeyCertPair(KeyCertPair):
    """Load a PEM formatted key and certificate pair from files.

    :param key_path: Path to the PEM formatted RSA private key file.
    :param cert_path: Path to the PEM formatted certificate file.
    :param passphrase: Pass phrase for encryption of the private key.
    """

    def __init__(self, key_path: Path, cert_path: Path, passphrase: str | None) -> None:
        self._key_path = pathlib.Path(key_path) if not isinstance(key_path, pathlib.Path) else key_path
        self._cert_path = pathlib.Path(cert_path) if not isinstance(cert_path, pathlib.Path) else cert_path

        with self._cert_path.open("rb") as _c:
            cert = x509.load_pem_x509_certificate(_c.read())

        _passphrase = bytes(passphrase, "utf-8") if passphrase is not None else None

        with self._key_path.open("rb") as _k:
            key = serialization.load_pem_private_key(_k.read(), password=_passphrase)

        super().__init__(key, cert)

        self.passphrase = passphrase

    @contextmanager
    def tempfiles(self) -> Generator:
        """Accessor for temporary certificate files."""
        yield self

    @property
    def key_path(self) -> str:
        """Path to the key file."""
        return self._key_path.as_posix()

    @property
    def cert_path(self) -> str:
        """Path to the certificate file."""
        return self._cert_path.as_posix()
