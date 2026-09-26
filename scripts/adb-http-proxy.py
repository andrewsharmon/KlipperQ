#!/usr/bin/env python3
"""Small localhost HTTP/HTTPS proxy intended for use through `adb reverse`."""

import argparse
import select
import socket
import socketserver
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError
from urllib.request import Request, urlopen


HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "proxy-connection",
}


class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_CONNECT(self):
        host, separator, port_text = self.path.rpartition(":")
        if not separator:
            host, port_text = self.path, "443"
        try:
            upstream = socket.create_connection((host, int(port_text)), timeout=20)
        except (OSError, ValueError) as exc:
            self.send_error(502, str(exc))
            return
        self.send_response(200, "Connection established")
        self.end_headers()
        sockets = (self.connection, upstream)
        try:
            while True:
                readable, _, exceptional = select.select(sockets, [], sockets, 60)
                if exceptional or not readable:
                    break
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    destination = upstream if source is self.connection else self.connection
                    destination.sendall(data)
        finally:
            upstream.close()

    def _proxy_http(self):
        if not self.path.startswith(("http://", "https://")):
            self.send_error(400, "Proxy request requires an absolute URL")
            return
        headers = {key: value for key, value in self.headers.items()
                   if key.lower() not in HOP_HEADERS and key.lower() != "host"}
        body = None
        if "Content-Length" in self.headers:
            body = self.rfile.read(int(self.headers["Content-Length"]))
        request = Request(self.path, data=body, headers=headers,
                          method=self.command)
        try:
            response = urlopen(request, timeout=60)
        except HTTPError as exc:
            response = exc
        except OSError as exc:
            self.send_error(502, str(exc))
            return
        with response:
            self.send_response(response.status, response.reason)
            for key, value in response.headers.items():
                if key.lower() not in HOP_HEADERS:
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
        self.close_connection = True

    do_GET = _proxy_http
    do_HEAD = _proxy_http
    do_POST = _proxy_http

    def log_message(self, message, *args):
        print("%s - %s" % (self.address_string(), message % args), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    with ThreadingServer((args.bind, args.port), ProxyHandler) as server:
        print("ADB HTTP proxy listening on %s:%d" % server.server_address,
              flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
