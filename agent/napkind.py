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
import logging
import sys
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
parser.add_option("-l", "--logfile", action="store", dest="logfile", default=None)
parser.add_option("-L", "--loglevel", action="store", dest="loglevel", default='INFO')
parser.add_option("-p", "--pidfile", action="store", dest="pidfile")
parser.add_option("-b", "--bind-address", action="store", dest="bind_addr", default="")
parser.add_option("-P", "--bind-port", action="store", dest="bind_port", type="int", default=12200)
parser.add_option("-S", "--state-dir", action="store", dest="statedir")
parser.add_option("-c", "--certificate", action="store", dest="certificate")
parser.add_option("-k", "--key", action="store", dest="key")
parser.add_option("-a", "--ca-certificate", action="store", dest="cacert")
(options, args) = parser.parse_args(sys.argv[1:])

logging.basicConfig(filename=options.logfile, level=getattr(logging, options.loglevel))
logging.debug('hello, this is napkind')

if options.daemonize:
    logfile = options.logfile
    if logfile is None:
        logfile = "/dev/null"
    stdout_log = open(logfile, 'a+', 0)
    stderr_log = open(logfile, 'a+', 0)
    dev_null = open('/dev/null', 'r+')

    os.dup2(stderr_log.fileno(), 2)
    os.dup2(stdout_log.fileno(), 1)
    os.dup2(dev_null.fileno(), 0)
    sys.stderr = stderr_log
    sys.stdout = stdout_log
    sys.stdin = dev_null

    pid = os.fork()
    if pid > 0:
        os._exit(0)
    os.umask(napkin.helpers.octal('0022'))
    os.setsid()
    os.chdir("/")
    pid = os.fork()
    if pid > 0:
        os._exit(0)

    if options.pidfile is not None:
        pid = os.getpid()
        pf = open(options.pidfile, 'w')
        pf.write("%d\n" % pid)
        pf.close()

def do_run(manifest, options, conn, addr):
    (fd, tmpname) = tempfile.mkstemp('', '.napkin.conf.', options.statedir)
    try:
        napkin.helpers.file_fetcher(options.manifest, lambda x: os.write(fd, x.encode('utf-8')))
        os.close(fd)
        os.rename(tmpname, os.path.join(options.statedir, "napkin.conf"))
    except:
        logging.exception("failed to download napkin.conf")
        os.close(fd)
        os.unlink(tmpname)
        if not os.path.exists(os.path.join(options.statedir, "napkin.conf")):
            return False
    manifest.read(os.path.join(options.statedir, "napkin.conf"))
    manifest.run()
    logging.debug("executed manifest =\n%s" % manifest)
    return True

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
        self.wfile.write("HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 3\r\n\r\n1\r\n")

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
