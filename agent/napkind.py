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
parser.add_option("-m", "--manifest", action="store", dest="manifest")
parser.add_option("-r", "--report", action="store", dest="report")
parser.add_option("-l", "--logconfig", action="store", dest="logconfig", default='/etc/napkin/logging.conf')
parser.add_option("-L", "--logfile", action="store", dest="logfile", default='/var/log/napkind')
parser.add_option("-p", "--pidfile", action="store", dest="pidfile")
parser.add_option("-b", "--bind-address", action="store", dest="bind_addr", default="")
parser.add_option("-P", "--bind-port", action="store", dest="bind_port", type="int", default=12200)
parser.add_option("-S", "--state-dir", action="store", dest="statedir")
parser.add_option("-c", "--certificate", action="store", dest="certificate")
parser.add_option("-k", "--key", action="store", dest="key")
parser.add_option("-a", "--ca-certificate", action="store", dest="cacert")
(options, args) = parser.parse_args(sys.argv[1:])

logging.config.fileConfig(options.logconfig)
logging.debug('hello, this is napkind')

if options.daemonize:
    napkin.helpers.daemonize(options.logfile, options.pidfile)

def do_run(manifest, options, conn, addr):
    (fd, tmpname) = tempfile.mkstemp('', '.napkin.conf.', options.statedir)
    ret = False
    try:
        napkin.helpers.file_fetcher(options.manifest, lambda x: os.write(fd, x.encode('utf-8')))
        os.close(fd)
        os.rename(tmpname, os.path.join(options.statedir, "napkin.conf"))
        ret = True
    except:
        logging.exception("failed to download napkin.conf")
        os.close(fd)
        os.unlink(tmpname)
        if not os.path.exists(os.path.join(options.statedir, "napkin.conf")):
            return False
    manifest.read(os.path.join(options.statedir, "napkin.conf"))
    manifest.run()
    logging.debug("executed manifest =\n%s" % manifest)
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
    if options.certificate:
        cmd += ["--cert", options.certificate]
        if options.key:
            cmd += ["--key", options.key]
    if options.cacert:
        cmd += ["--cacert", options.cacert]
    cmd += [options.report]
    p = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = p.communicate()
    os.unlink(tmpname)
    if p.returncode != 0:
        logging.error("sending report failed: %d: %s" % (p.returncode, stderr))

manifest = napkin.manifest()

if not do_run(manifest, options, None, None):
    os._exit(1)

def do_monitoring():
    while True:
        time_left = manifest.get_delay()
        if time_left is None:
            break
        time.sleep(time_left)
        manifest.monitor()
        send_report(manifest.get_report())
    logging.error("monitor dying")

monitor = threading.Thread(target=do_monitoring)
monitor.start()

class AgentRequestHandler(napkin.api.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    def do_GET(self):
        hostname = None
        for i in self.request.peercert['subject']:
            if i[0][0] == 'commonName':
                hostname = i[0][1]
        if hostname != config['master']:
            logging.warning("Request for %s from %s not from configured master %s" % (self.path, hostname, config['master']))
            self.send_error(401)
            self.wfile.write("Request not from configured master!")
            return
        if self.path == "/run":
            result = do_run(manifest, options, None, None)
        else:
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
                certfile=options.certificate,
                cert_reqs=napkin.api.CERT_REQ)

try:
    server.serve_forever()
finally:
    manifest.clear_monitor()
    monitor.join()
