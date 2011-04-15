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
parser.add_option("-C", "--config", action="store", dest="conffile", default="/etc/napkin/napkind.conf")
parser.add_option("-m", "--manifest", action="store", dest="manifest")
parser.add_option("-r", "--report", action="store", dest="report")
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
(options, args) = parser.parse_args(sys.argv[1:])

if options.conffile and os.path.exists(options.conffile):
    d = {}
    napkin.helpers.execfile(options.conffile, d, d)
    for i in d:
        if getattr(options, i) is None:
            setattr(options, i, d[i])
    del d

if not options.logconfig:
    options.logconfig = "/etc/napkin/logging.conf"
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
if not options.cacert:
    options.cacert = "/etc/napkin/ca.crt"
if not options.cert:
    options.cert = "/etc/napkin/agent.crt"
if not options.key:
    options.key = "/etc/napkin/agent.key"

logging.config.fileConfig(options.logconfig)

logger = logging.getLogger("napkin.agent")
stderr_handler = logging.StreamHandler(sys.stderr)
logger.addHandler(stderr_handler)

logger.debug('hello, this is napkind')

def do_run(manifest, options, conn, addr):
    (fd, tmpname) = tempfile.mkstemp('', '.napkin.conf.', options.statedir)
    ret = False
    try:
        napkin.helpers.file_fetcher(options.manifest, lambda x: os.write(fd, napkin.helpers.to_bytes(x)), options)
        os.close(fd)
        os.rename(tmpname, os.path.join(options.statedir, "napkin.conf"))
        ret = True
    except:
        logger.exception("failed to download napkin.conf")
        os.close(fd)
        os.unlink(tmpname)
        if not os.path.exists(os.path.join(options.statedir, "napkin.conf")):
            return False
    manifest.read(os.path.join(options.statedir, "napkin.conf"))
    manifest.run()
    logger.debug("executed manifest =\n%s" % manifest)
    return ret

def send_report(report_data):
    if not options.report:
        return
    if not report_data:
        return
    (fd, tmpname) = tempfile.mkstemp()
    os.write(fd, str(report_data).encode("utf-8"))
    os.close(fd)
    cmd = ["curl", "-s", "-S", "-L", "-f", "--data-binary", "@%s" % tmpname, "-H", "Content-Type: application/x-napkin-report"]
    if options.cert:
        cmd += ["--cert", options.cert]
        if options.key:
            cmd += ["--key", options.key]
    if options.cacert:
        cmd += ["--cacert", options.cacert]
    cmd += [options.report]
    p = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = p.communicate()
    os.unlink(tmpname)
    if p.returncode != 0:
        logger.error("sending report failed: %d: %s" % (p.returncode, stderr))

manifest = napkin.manifest()

if not do_run(manifest, options, None, None):
    logger.error("unable to get initial manifest")
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
            logger.warning("Request for %s from %s not from configured master %s" % (self.path, hostname, config['master']))
            self.send_error(401)
            self.wfile.write("Request not from configured master!")
            return
        if self.path == "/run":
            result = do_run(manifest, options, None, None)
        else:
            logger.warning("Unknown request for %s" % self.path)
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
    server.serve_forever()
finally:
    manifest.stop_monitor()
    monitor.join()
