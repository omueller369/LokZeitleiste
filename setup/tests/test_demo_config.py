import importlib.util
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('demo_config',ROOT/'setup/demo-config.py')
config=importlib.util.module_from_spec(spec);spec.loader.exec_module(config)


class DemoConfigTest(unittest.TestCase):
    def test_dns_rejects_wrong_or_ipv6_records(self):
        row=lambda family,address:(family,socket.SOCK_STREAM,6,'',(address,80))
        with patch.object(config.socket,'getaddrinfo',return_value=[row(socket.AF_INET,'212.227.86.251')]):
            config.dns('io-goerlitz.eu','212.227.86.251')
        for records in ([row(socket.AF_INET,'192.0.2.1')],[],[row(socket.AF_INET,'212.227.86.251'),row(socket.AF_INET6,'2001:db8::1')]):
            with patch.object(config.socket,'getaddrinfo',return_value=records),self.assertRaises(ValueError):
                config.dns('io-goerlitz.eu','212.227.86.251')

    def test_origin_and_secure_cookies_keep_existing_credentials(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'.env.test';path.write_text('MYSQL_PASSWORD=unchanged\nCOOKIE_SECURE=false\nPUBLIC_ORIGIN=http://localhost:8080\n')
            config.update_env(path,'io-goerlitz.eu');first=path.read_bytes()
            config.update_env(path,'io-goerlitz.eu');self.assertEqual(first,path.read_bytes())
            self.assertIn('MYSQL_PASSWORD=unchanged',path.read_text())
            self.assertIn('PUBLIC_ORIGIN=https://io-goerlitz.eu',path.read_text())
            self.assertIn('COOKIE_SECURE=true',path.read_text());self.assertEqual(path.stat().st_mode&0o777,0o600)
            linked=Path(name)/'link';linked.symlink_to(path)
            with self.assertRaises(ValueError):config.update_env(linked,'io-goerlitz.eu')

    def test_webroot_only_http_and_tls_proxy(self):
        http=config.apache('http','io-goerlitz.eu');https=config.apache('https','io-goerlitz.eu')
        self.assertNotIn('ProxyPass',http);self.assertIn('acme-challenge',http)
        self.assertIn('https://io-goerlitz.eu',http)
        self.assertIn('127.0.0.1:8000',https);self.assertIn('SSLEngine On',https)
        self.assertIn('ProxyPreserveHost On',https)
        for domain in ['example.com\nProxyPass / http://evil/','../bad','-bad.example','EXAMPLE.COM']:
            with self.assertRaises(ValueError):config.apache('https',domain)


if __name__=='__main__':unittest.main()
