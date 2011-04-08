#!/usr/bin/python -tt
# vim:set ts=4 sw=4 expandtab:
# 
# napkin - Linux-specific types and monitors
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
import napkin

try:
    long_type = long
except NameError:
    long = int

class m_nic(napkin.monitor):
    properties = {
    }
    def fetch(self):
        ret = None
        with open('/proc/net/dev', 'r') as f:
            while True:
                line = f.readline()
                if not line:
                    break
                fields = line.strip().split()
                if len(fields) < 17:
                    continue
                if fields[0] == self.name + ":":
                    ret = {'in': {'packets': long(fields[2]), 'bytes': long(fields[1])},
                           'out': {'packets': long(fields[10]), 'bytes': long(fields[9])}}
                    break
        return ret

class m_uptime(napkin.monitor):
    properties = {
    }
    def fetch(self):
        return float(open('/proc/uptime', 'r').readline().split()[0])

class m_memory(napkin.monitor):
    name = ""
    properties = {
    }
    def fetch(self):
        meminfo = {}
        with open('/proc/meminfo', 'r') as fp:
            while True:
                line = fp.readline()
                if not line:
                    break
                line = line.strip()
                fields = line.split()
                meminfo[fields[0][:-1]] = long(fields[1])
        return {'total': meminfo['MemTotal'],
            'free': meminfo['MemFree'],
            'buffers': meminfo['Buffers'],
            'cached': meminfo['Cached'],
            'realfree': meminfo['MemFree'] + meminfo['Buffers'] + meminfo['Cached']}

class m_num_processes(napkin.monitor):
    name = ""
    properties = {
    }
    def fetch(self):
        ret = 0
        for i in filter(lambda x: x.isdigit(), os.listdir("/proc")):
            ret += 1
        return ret

class m_loadavg(napkin.monitor):
    name = ""
    properties = {
    }
    def fetch(self):
        loadavg = os.getloadavg()
        return {'1min': loadavg[0], '5min': loadavg[1], '15min': loadavg[2]}

class m_cpu(napkin.monitor):
    properties = {
    }
    def fetch(self):
        return 0

class m_cpus(napkin.monitor):
    properties = {
    }
    def fetch(self):
        return 0
