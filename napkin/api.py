#!/usr/bin/python -tt
# vim:set ts=4 sw=4 expandtab:
# 
# napkin - API interfaces
# Copyright (C) 2011 Daniel Hokka Zakrisson <daniel@hozac.com>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
except:
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
try:
    from ssl import wrap_socket as ssl_wrap_socket, CERT_REQUIRED as CERT_REQ
except:
    import OpenSSL
    def ssl_wrap_socket(conn, keyfile=None, certfile=None, ca_certs=None, cert_reqs=None, server_side=None):
        ctx = OpenSSL.SSL.Context(OpenSSL.SSL.SSLv23_METHOD)
        if keyfile is not None:
            ctx.use_privatekey_file(keyfile)
        if certfile is not None:
            ctx.use_certificate_file(certfile)
        if ca_certs is not None:
            ctx.load_client_ca(ca_certs)
        if cert_reqs == 1:
            ctx.set_verify(OpenSSL.SSL.SSL_VERIFY_PEER)
        return OpenSSL.SSL.Connection(ctx, conn)
import json

class SecureHTTPServer(HTTPServer):
    def __init__(self, *args, **kwargs):
        self.ssl_wrap_args = {'server_side': True}
        for i in ['keyfile', 'certfile', 'ca_certs', 'cert_reqs']:
            if i in kwargs:
                self.ssl_wrap_args[i] = kwargs[i]
                del kwargs[i]
        HTTPServer.__init__(self, *args, **kwargs)
    def get_request(self):
        conn, addr = self.socket.accept()
        sconn = ssl_wrap_socket(conn, **self.ssl_wrap_args)
        return (sconn, addr)

def serialize(data):
    return json.dumps(data)
def deserialize(data):
    return json.loads(data)

if __name__ == "__main__":
    import sys
    kwargs = {}
    for i in sys.argv:
        fields = i.split("=")
        kwargs[fields[0]] = fields[1]
    SimpleHTTPRequestHandler.protocol_version = "HTTP/1.0"
    s = SecureHTTPServer(('', 12201), SimpleHTTPRequestHandler, **kwargs)
    s.serve_forever()
