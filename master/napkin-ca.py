#!/usr/bin/python -tt
# vim:set ts=4 sw=4 expandtab:
# 
# napkin - signs CSRs from agents
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
import optparse
import subprocess
import tempfile
import socket
import napkin.db
import napkin.helpers

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
logger = logging.getLogger("napkin.ca")
stderr_handler = logging.StreamHandler(sys.stderr)
logger.addHandler(stderr_handler)

parser = optparse.OptionParser(version="0.1")
parser.add_option("-s", "--sign", action="store_true", dest="sign")
parser.add_option("-c", "--create", action="store_true", dest="create")
parser.add_option("-m", "--create-master", action="store_true", dest="master")
(options, args) = parser.parse_args(sys.argv[1:])

if options.sign:
    files = os.listdir(config['csrdir'])
    (fd, tmpname) = tempfile.mkstemp()
    os.close(fd)
    napkin.db.connect(config)
    cur = napkin.db.cursor()
    for i in files:
        if i.startswith(".") or not i.endswith(".csr"):
            continue
        csr = os.path.join(config['csrdir'], i)
        hostname = i.replace(".csr", "")
        crt = csr.replace(".csr", ".crt")
        try:
            cur.execute("SELECT aid FROM agents WHERE hostname = '%s'" % hostname)
            serial = cur.fetchone()
            if serial is None:
                logger.error("unable to find %s in database", hostname)
                continue
            else:
                serial = serial[0] + 2
            napkin.helpers.replace_file(os.path.join(config['confdir'], "agent-template.ct"),
                                        tmpname, {"@HOSTNAME@": hostname, "@SERIAL@": serial[0]})
            cmd = ["certtool", "--generate-certificate",
                   "--outfile", crt, "--load-request", csr,
                   "--load-ca-certificate", config['cacert'],
                   "--load-ca-privkey", config['cakey'], "--template",
                   os.path.join(config['confdir'], "agent-template.ct")]
            ret = subprocess.call(cmd)
            if ret == 0:
                logger.info("signed %s", hostname)
                os.unlink(csr)
        except:
            try:
                os.unlink(crt)
            except:
                pass
            logger.error("failed to generate certificate for %s: %s", hostname, sys.exc_info()[1])
    os.unlink(tmpname)
    napkin.db.close()
elif options.create:
    if not os.path.exists(config['cakey']):
        cmd = ["certtool", "--bits", "2048", "--generate-privkey",
               "--outfile", config['cakey']]
        ret = subprocess.call(cmd)
        if ret == 0:
            logger.info("generated %s", config['cakey'])
        else:
            logger.error("failed to generate %s", config['cakey'])
            os._exit(1)
    if not os.path.exists(config['cacert']):
        cmd = ["certtool", "--generate-self-signed", "--outfile",
               config['cacert'], "--load-privkey", config['cakey']]
        ret = subprocess.call(cmd)
        if ret == 0:
            logger.info("generated %s", config['cacert'])
        else:
            logger.error("failed to generate %s", config['cacert'])
            os._exit(1)
elif options.master:
    did_key = False
    if not os.path.exists(config['key']):
        cmd = ["certtool", "--bits", "2048", "--generate-privkey",
               "--outfile", config['key']]
        ret = subprocess.call(cmd)
        if ret == 0:
            logger.info("generated %s", config['key'])
            did_key = True
        else:
            logger.error("failed to generate %s", config['key'])
            os._exit(1)
    csr = config['cert'] + ".csr"
    (fd, tmpname) = tempfile.mkstemp()
    os.close(fd)
    napkin.helpers.replace_file(os.path.join(config['confdir'], "master-template.ct"),
                                tmpname, {'@HOSTNAME@': socket.gethostname()})
    if not os.path.exists(csr) or did_key:
        cmd = ["certtool", "--generate-request",
               "--load-privkey", config['key'],
               "--outfile", csr, "--template",
               tmpname]
        ret = subprocess.call(cmd)
        if ret == 0:
            logger.info("generated %s", csr)
        else:
            logger.error("failed to generate %s", csr)
            os._exit(1)
    if not os.path.exists(config['cert']) or did_key:
        cmd = ["certtool", "--generate-certificate",
               "--outfile", config['cert'], "--load-request", csr,
               "--load-ca-certificate", config['cacert'],
               "--load-ca-privkey", config['cakey'], "--template",
               tmpname]
        ret = subprocess.call(cmd)
        if ret == 0:
            logger.info("generated %s", config['cert'])
        else:
            logger.error("failed to generate %s", config['cert'])
            os._exit(1)
    os.unlink(tmpname)
    os.unlink(csr)
else:
    sys.stderr.write("%s: one of --sign, --create or --create-master is required\n" % sys.argv[0])
    os._exit(1)
