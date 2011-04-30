#!/usr/bin/python -tt
# vim:set ts=4 sw=4 expandtab:
# 
# napkin - napkind runs on clients and monitors resources and does things when told
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
import logging
import logging.config
import optparse
import socket
import tempfile
import time
import select
import subprocess
import threading

import napkin
import napkin.helpers
import napkin.api

parser = optparse.OptionParser(version="0.1")
parser.add_option("-d", "--daemonize", action="store_true", dest="daemonize")
parser.add_option("-D", "--confdir", action="store", dest="confdir", default="/etc/napkin")
parser.add_option("-C", "--config", action="store", dest="conffile", default="/etc/napkin/napkind.conf")
parser.add_option("-m", "--manifest", action="store", dest="manifest")
parser.add_option("-r", "--report", action="store", dest="report")
parser.add_option("-R", "--register", action="store", dest="register")
parser.add_option("-l", "--logconfig", action="store", dest="logconfig")
parser.add_option("-L", "--logfile", action="store", dest="logfile")
parser.add_option("-p", "--pidfile", action="store", dest="pidfile")
parser.add_option("-b", "--bind-address", action="store", dest="bind_addr")
parser.add_option("-P", "--bind-port", action="store", dest="bind_port", type="int")
parser.add_option("-S", "--statedir", action="store", dest="statedir")
parser.add_option("-c", "--cert", action="store", dest="cert")
parser.add_option("-k", "--key", action="store", dest="key")
parser.add_option("-a", "--cacert", action="store", dest="cacert")
parser.add_option("-M", "--master", action="store", dest="master")
parser.add_option("-T", "--no-tls", action="store_false", dest="tls", default=True)
(options, args) = parser.parse_args(sys.argv[1:])

if options.conffile and os.path.exists(options.conffile):
    d = {}
    napkin.helpers.execfile(options.conffile, d, d)
    for i in d:
        if getattr(options, i) is None:
            setattr(options, i, d[i])
    del d

def file_if_exists(fn):
    if os.path.exists(fn):
        return fn
    else:
        return None

if not options.logconfig:
    options.logconfig = "%s/logging.conf" % options.confdir
if not options.logfile:
    options.logfile = "/var/log/napkind"
if not options.pidfile:
    options.pidfile = "/var/run/napkind.pid"
if not options.bind_addr:
    options.bind_addr = ""
if not options.bind_port:
    options.bind_port = 12200
if not options.statedir:
    options.statedir = "/var/lib/napkin"
if not options.manifest and options.master:
    options.manifest = "https://%s:12201/napkin/manifest" % options.master
if not options.report and options.master:
    options.report = "https://%s:12201/napkin/report" % options.master
if not options.register and options.master:
    options.register = "https://%s:12201/napkin/register" % options.master
if not options.cacert and options.tls:
    options.cacert = "%s/ca.crt" % options.confdir
if not options.cert and options.tls:
    options.cert = "%s/agent.crt" % options.confdir
if not options.key and options.tls:
    options.key = "%s/agent.key" % options.confdir

logging.config.fileConfig(options.logconfig)

logger = logging.getLogger("napkin.agent")
stderr_handler = logging.StreamHandler(sys.stderr)
logger.addHandler(stderr_handler)

logger.debug('hello, this is napkind')

def do_run(manifest, options, conn, addr):
    (fd, tmpname) = tempfile.mkstemp('', '.napkin.conf.', options.statedir)
    try:
        napkin.helpers.file_fetcher(options.manifest, lambda x: os.write(fd, napkin.helpers.to_bytes(x)), options)
        os.close(fd)
        os.rename(tmpname, os.path.join(options.statedir, "napkin.conf"))
    except:
        e = sys.exc_info()[1]
        logger.error("failed to download napkin.conf: %s", str(e))
        os.close(fd)
        os.unlink(tmpname)
        if not os.path.exists(os.path.join(options.statedir, "napkin.conf")):
            return False
    manifest.read(os.path.join(options.statedir, "napkin.conf"))
    manifest.run()
    logger.debug("executed manifest =\n%s", manifest)
    return True

def send_report(report_data):
    if not options.report:
        return
    if not report_data:
        return
    (fd, tmpname) = tempfile.mkstemp()
    os.write(fd, napkin.api.serialize(report_data))
    os.close(fd)
    try:
        napkin.helpers.file_sender(options.report, tmpname, "application/x-napkin-report", options)
    except:
        e = sys.exc_info()[1]
        logger.error("sending report failed: %s", e)
    os.unlink(tmpname)

if options.master:
    import napkin.providers
    import socket
    napkin.providers.load()
    data = {'hostname': socket.gethostname(),
            'providers': napkin.providers.providers,
            'version': 1}
    (fd, tmpname) = tempfile.mkstemp()
    os.close(fd)
    if options.tls:
        if not os.path.exists(options.cert):
            if not os.path.exists(options.key):
                if subprocess.call(["certtool", "--bits", "2048", "-p",
                                    "--outfile", options.key]) != 0:
                    logger.error("failed to generate private key")
                    os._exit(1)
            csrpath = options.cert.replace(".crt", ".csr")
            if not os.path.exists(csrpath):
                napkin.helpers.replace_file(os.path.join(options.confdir, "agent-template.ct"),
                                            tmpname, {'@HOSTNAME@': data['hostname']})
                if subprocess.call(["certtool", "--template", tmpname,
                                    "-q", "--load-privkey", options.key,
                                    "--outfile", csrpath]) != 0:
                    logger.error("failed to generate csr")
                    os._exit(1)
            data['csr'] = open(csrpath, 'r').read()
    f = open(tmpname, 'w')
    napkin.api.serialize(data, f)
    f.close()
    failure = True
    try:
        ret = napkin.helpers.file_sender(options.register, tmpname, "application/x-napkin-register", options).decode("utf-8")
        if not napkin.api.deserialize(ret):
            raise Exception("received failure from master: %s" % ret)
        failure = False
    except:
        logger.exception("registering with %s failed", options.register)
    os.unlink(tmpname)
    if failure:
        os._exit(1)
    if 'csr' in data:
        logger.warning("waiting for cert...")
        while True:
            time.sleep(60)

manifest = napkin.manifest()

if not do_run(manifest, options, None, None):
    logger.error("unable to execute initial manifest")
    os._exit(1)

if options.daemonize:
    logger.removeHandler(stderr_handler)
    del stderr_handler
    napkin.helpers.daemonize(options.logfile, options.pidfile)

def do_monitoring():
    while True:
        time_left = manifest.get_delay()
        if time_left is None:
            break
        time.sleep(time_left)
        manifest.monitor()
        send_report(manifest.get_report())
    logger.error("monitor dying")

if manifest.get_delay() is not None:
    monitor = threading.Thread(target=do_monitoring)
    monitor.start()

class AgentRequestHandler(napkin.api.BaseHTTPRequestHandler):
    server_version = "napkin/0.1"
    protocol_version = "HTTP/1.0"
    def do_GET(self):
        hostname = None
        for i in self.request.peercert['subject']:
            if i[0][0] == 'commonName':
                hostname = i[0][1]
        if hostname != options.master:
            logger.warning("Request for %s from %s not from configured master %s", self.path, hostname, config['master'])
            self.send_error(401)
            self.wfile.write("Request not from configured master!")
            return
        if self.path == "/run":
            result = do_run(manifest, options, None, None)
        else:
            logger.warning("Unknown request for %s", self.path)
            self.send_error(404)
            self.wfile.write("Unknown request %s" % self.path)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "3")
        self.end_headers()
        if result:
            self.wfile.write("1\r\n")
        else:
            self.wfile.write("0\r\n")

server = napkin.api.SecureHTTPServer((options.bind_addr, options.bind_port),
            AgentRequestHandler,
                keyfile=options.key,
                ca_certs=options.cacert,
                certfile=options.cert,
                cert_reqs=napkin.api.CERT_REQ)

try:
    server.serve_forever(None)
finally:
    manifest.stop_monitor()
    monitor.join()
