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

files = os.listdir(config['csrdir'])
for i in files:
    if i.startswith("."):
        continue
    if not i.endswith(".csr"):
        continue
    f = os.path.join(config['csrdir'], i)
    try:
        ret = subprocess.call(["certtool", "--generate-certificate",
                               "--outfile", f.replace(".csr", ".crt"),
                               "--load-request", f, "--load-ca-certificate",
                               config['cacert'], "--load-ca-privkey",
                               config['cakey'], "--template",
                               os.path.join(config['confdir'], "template.ct")])
        if ret == 0:
            logger.info("signed %s", i.replace(".csr", ""))
            os.unlink(os.path.join(config['csrdir'], i))
    except:
        pass
