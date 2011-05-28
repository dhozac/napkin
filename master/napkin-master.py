#!/usr/bin/python -tt
# vim:set ts=4 sw=4 expandtab:
# 
# napkin - processes reports from agents
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

import os
import sys
import time
import logging
import optparse
import shutil
import napkin.helpers
import napkin.api
import napkin.db

config = {}
napkin.helpers.execfile('/etc/napkin/master.conf', config, config)
root_logger = logging.getLogger("napkin")
log_handler = logging.FileHandler(config['logfile'])
formatter = logging.Formatter("%(asctime)s napkin: %(message)s")
log_handler.setFormatter(formatter)
root_logger.addHandler(log_handler)
root_logger.setLevel(getattr(logging, config['loglevel']))
del root_logger
del formatter
del log_handler
logger = logging.getLogger("napkin.master")

napkin.db.connect(config)

def process_report(hostname, rfp, wfp, resp):
    if hostname is None:
        resp.send_error(400, "No common name found in certificate!\r\n")
        return
    length = resp.headers.get("content-length", None)
    if length is None:
        resp.send_error(400, "No Content-Length in request!\r\n")
        return
    length = int(length)
    data = ""
    while length > 0:
        ret = rfp.read(length)
        length -= len(ret)
        data += ret.decode("utf-8")
    report = napkin.api.deserialize(data)
    logger.debug("%s: %s", hostname, report)
    cur = napkin.db.cursor()
    cur.execute("UPDATE agents SET last_report = %d WHERE hostname = '%s'" % (time.time(), hostname))
    resp.send_response(200)
    resp.send_header("Content-Length", "3")
    resp.end_headers()
    wfp.write("1\r\n".encode("utf-8"))

manifests = {}
def create_manifest(hostname, rfp, wfp, resp):
    if hostname is None:
        resp.send_error(400, "No common name found in certificate!\r\n")
        return
    if hostname not in manifests:
        manifests[hostname] = napkin.manifest()
    providers = []
    cur = napkin.db.cursor()
    cur.execute("SELECT p.provider FROM providers AS p, agents AS a WHERE " +
                "a.aid = p.aid AND a.hostname = '%s'" % hostname)
    for i in cur:
        providers.append(i[0])
    manifests[hostname].read([os.path.join(config['manifestdir'], 'common'),
                              os.path.join(config['manifestdir'], hostname)],
                             providers, hostname)
    r = repr(manifests[hostname]).encode("utf-8")
    resp.send_response(200)
    resp.send_header("Content-Type", "application/x-napkin-manifest")
    resp.send_header("Content-Length", "%d" % len(r))
    resp.send_header("Last-Modified", time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(max(manifests[hostname].mtime.values()))))
    resp.end_headers()
    wfp.write(r)

def send_file(hostname, path, rfp, wfp, resp):
    if hostname is None:
        resp.send_error(400, "No common name found in certificate!\r\n")
        return
    filename = None
    name = path[path.index('/files/') + 6:]
    for p in (os.path.join(config['filesdir'], hostname), config['filesdir']):
        f = os.path.join(p, name)
        if os.path.exists(f):
            filename = f
            break
    if filename is None or not os.path.isfile(filename):
        resp.send_error(404, "No such file could be found!\r\n")
        return
    st = os.stat(filename)
    resp.send_response(200)
    resp.send_header("Content-Length", "%d" % (st.st_size))
    resp.send_header("Content-Type", "application/x-napkin-file")
    resp.send_header("Last-Modified", time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(st.st_mtime)))
    resp.end_headers()
    f = open(filename, 'rb')
    shutil.copyfileobj(f, wfp)
    f.close()

def register(hostname, rfp, wfp, resp):
    length = resp.headers.get("content-length", None)
    if length is None:
        resp.send_error(400, "No Content-Length in request!\r\n")
        return
    length = int(length)
    data = ""
    while length > 0:
        ret = rfp.read(length)
        length -= len(ret)
        data += ret.decode("utf-8")
    registration = napkin.api.deserialize(data)
    logger.debug("%s: %s", hostname, registration)
    if ('hostname' not in registration or
        'providers' not in registration or
        'version' not in registration):
        resp.send_error(400, "Invalid registration\r\n")
        return
    if hostname is not None and registration['hostname'] != hostname:
        logger.warning("%s registered as %s", hostname, registration['hostname'])
        resp.send_error(401, "Attempt to register as different hostname\r\n")
        return
    if hostname is None and registration['csr']:
        logger.info("%s requesting certificate", registration['hostname'])
        f = open(os.path.join(config['csrdir'], registration['hostname'] + ".csr"), 'w')
        f.write(registration['csr'])
        f.close()
    elif hostname is None:
        logger.warning("%s has no certificate, and didn't request one", registration['hostname'])
    cur = napkin.db.cursor()
    cur.execute("SELECT aid FROM agents WHERE hostname = '%s'" % registration['hostname'])
    row = cur.fetchone()
    if row is None:
        cur.execute("INSERT INTO agents (aid, hostname, last_report) VALUES (NULL, '%s', %d)" % (hostname, time.time()))
        napkin.db.commit()
        # FIXME
        cur.execute("SELECT aid FROM agents WHERE hostname = '%s'" % registration['hostname'])
        row = cur.fetchone()
    else:
        cur.execute("UPDATE agents SET last_report = %d WHERE aid = %d" % (time.time(), row[0]))
    aid = row[0]
    cur.execute("DELETE FROM providers WHERE aid = %d" % aid)
    for i in registration['providers']:
        cur.execute("INSERT INTO providers VALUES (%d, '%s')" % (aid, i))
    napkin.db.commit()
    resp.send_response(200)
    resp.send_header("Content-Length", "3")
    resp.end_headers()
    wfp.write("1\r\n".encode("utf-8"))

def get_certificate(hostname, rfp, wfp, resp, qs):
    if not qs.startswith("hostname="):
        resp.send_error(400, "Invalid query string specified: %s\r\n" % qs)
        logger.debug("invalid query string: %s", qs)
    hostname = qs[9:]
    filename = os.path.join(config['csrdir'], hostname + ".crt")
    if os.path.exists(filename):
        cst = os.stat(filename)
        ast = os.stat(config['cacert'])
        length = cst.st_size + 15 + ast.st_size
        resp.send_response(200)
        resp.send_header("Content-Length", length)
        resp.end_headers()
        f = open(config['cacert'], 'rb')
        shutil.copyfileobj(f, wfp)
        f.close()
        wfp.write("\r\n---split---\r\n".encode("utf-8"))
        f = open(filename, 'rb')
        shutil.copyfileobj(f, wfp)
        f.close()
        logger.info("sent certificate to %s", hostname)
    else:
        logger.debug("%s waiting on certificate", hostname)
        resp.send_error(404, "No such certificate yet\r\n")

if 'GATEWAY_INTERFACE' in os.environ:
    class Wrapper:
        def __init__(self):
            self.headers = {}
        def send_response(self, status):
            if hasattr(self, 'status'):
                return
            print("Status: %d" % status)
            self.status = status
        def send_error(self, status, msg):
            self.send_response(status)
            print("Content-Type: text/plain")
            print("")
            print(msg)
        def end_headers(self):
            print("")
        def send_header(self, header, value):
            print("%s: %s" % (header, value))
    resp = Wrapper()
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        if line.strip() == "":
            break
        (header, value) = line.split(":", 1)
        resp.headers[header.strip().lower()] = value.strip()
    hostname = os.environ['SSL_CLIENT_S_DN_CN']
    if os.environ['SCRIPT_NAME'].endswith("/report"):
        process_report(hostname, sys.stdin, sys.stdout, resp)
    elif os.environ['SCRIPT_NAME'].endswith("/manifest"):
        create_manifest(hostname, sys.stdin, sys.stdout, resp)
    elif os.environ['SCRIPT_NAME'].endswith("/cert"):
        get_certificate(hostname, sys.stdin, sys.stdout, resp, os.environ['QUERY_STRING'])
    elif '/files/' in os.environ['SCRIPT_NAME']:
        send_file(hostname, os.environ['SCRIPT_NAME'], sys.stdin, sys.stdout, resp)
    else:
        resp.send_error(500, "Invalid request filename")
else:
    if config['daemonize']:
        napkin.helpers.daemonize(config['logfile'], config['pidfile'])
    class MasterRequestHandler(napkin.api.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"
        server_version = "napkin/0.1"
        def send_error(self, status=400, msg=None):
            if msg:
                msg = msg.encode("utf-8")
            self.send_response(status)
            if msg:
                self.send_header("Content-Length", len(msg))
            self.end_headers()
            if msg:
                self.wfile.write(msg)
        def do_GET(self):
            try:
                hostname = None
                if self.request.peercert:
                    for i in self.request.peercert['subject']:
                        if i[0][0] == 'commonName':
                            hostname = i[0][1]
                logger.debug("%s GET %s", hostname, self.path)
                if self.path.startswith("/napkin"):
                    self.path = self.path[7:]
                if self.path == "/manifest":
                    create_manifest(hostname, self.rfile, self.wfile, self)
                elif self.path.startswith("/cert?hostname="):
                    get_certificate(hostname, self.rfile, self.wfile, self, self.path[6:])
                elif self.path.startswith("/files/"):
                    send_file(hostname, self.path, self.rfile, self.wfile, self)
                else:
                    self.send_error(404)
            except:
                logger.exception("failure in GET %s" % self.path)
                self.send_error(500)
        def do_POST(self):
            try:
                hostname = None
                if self.request.peercert:
                    for i in self.request.peercert['subject']:
                        if i[0][0] == 'commonName':
                            hostname = i[0][1]
                logger.debug("%s POST %s", hostname, self.path)
                if self.path.startswith("/napkin"):
                    self.path = self.path[7:]
                if self.path == "/report":
                    process_report(hostname, self.rfile, self.wfile, self)
                elif self.path == "/register":
                    register(hostname, self.rfile, self.wfile, self)
                else:
                    self.send_error(404)
            except:
                logger.exception("failure in POST %s" % self.path)
                self.send_error(500)
        def log_message(self, *args, **kwargs):
            pass

    server = napkin.api.SecureHTTPServer(('', 12201),
                MasterRequestHandler,
                    keyfile=config['key'],
                    ca_certs=config['cacert'],
                    certfile=config['cert'],
                    cert_reqs=napkin.api.CERT_OPT)

    try:
        server.serve_forever(None)
    except KeyboardInterrupt:
        pass
    except:
        logger.exception("Server crashed!")
