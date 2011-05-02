#!/usr/bin/python -tt
# vim:set ts=4 sw=4 expandtab:
# 
# napkin - instigates a run of the agents
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
import napkin.db

config = {}
napkin.helpers.execfile('/etc/napkin/master.conf', config, config)
root_logger = logging.getLogger("napkin")
log_handler = logging.FileHandler(config['logfile'])
formatter = logging.Formatter("%(asctime)s napkin-run: %(message)s")
log_handler.setFormatter(formatter)
root_logger.addHandler(log_handler)
root_logger.setLevel(getattr(logging, config['loglevel']))
del root_logger
del formatter
del log_handler
logger = logging.getLogger("napkin.run")

class opts:
    cacert = config['cacert']
    cert = config['cert']
    key = config['key']
options = opts()

if sys.argv[1] == "-a":
    hosts = []
    napkin.db.connect(config)
    cur = napkin.db.cursor()
    cur.execute("SELECT hostname FROM agents")
    for i in cur:
        hosts.append(i[0])
    napkin.db.close()
else:
    hosts = sys.argv[1:]

for i in hosts:
    sys.stdout.write("%s: " % i)
    try:
        napkin.helpers.file_fetcher("https://%s:12200/run" % i, lambda x: sys.stdout.write(x.decode("utf-8")), options)
    except:
        sys.stdout.write("0\n")
