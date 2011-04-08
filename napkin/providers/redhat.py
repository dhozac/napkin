#!/usr/bin/python -tt
# vim:set ts=4 sw=4 expandtab:
# 
# napkin - Red Hat Linux-derived specific types and monitors
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
import subprocess
import napkin

class t_service(napkin.resource):
    properties = {
        'name': {'required': True},
    }
    def ensure_present(self):
        ret = subprocess.call(["/sbin/chkconfig", self.name, "on"])
        ret = subprocess.call(["/sbin/service", self.name, "status"])
        if ret != 0:
            ret = subprocess.call(["/sbin/service", self.name, "start"])
            self.notify_subscribers('start')
            self.success = True
            return "%s started" % self.name
    def ensure_absent(self):
        if os.path.exists("/etc/init.d/%s" % self.name):
            ret = 0
            ret += subprocess.call(["/sbin/chkconfig", self.name, "off"])
            if os.path.exists("/var/lock/subsys/%s" % self.name):
                ret += subprocess.call(["/sbin/service", self.name, "stop"])
                self.notify_subscribers('stop')
                self.success = True
                return "%s stopped" % self.name
    ensure_running = ensure_present
    ensure_stopped = ensure_absent

class t_package(napkin.resource):
    properties = {
        'version': {},
    }
    def ensure_present(self):
        ret = subprocess.call(["yum", "-y", "-d", "1", "install", self.name])
        self.success = ret == 0
    def ensure_absent(self):
        ret = subprocess.call(["yum", "-y", "-d", "1", "remove", self.name])
        self.success = ret == 0
