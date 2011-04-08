#!/usr/bin/python -tt
# vim:set ts=4 sw=4 expandtab:
# 
# napkin - POSIX-specific types and monitors
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
import tempfile
import pwd
import grp
import subprocess
import napkin
import napkin.helpers

class t_file(napkin.resource):
    def_name = 'dest'
    properties = {
        'dest': {'required': True, 'help': 'destination filename'},
        'source': {},
        'filter': {},
        'owner': {},
        'group': {},
        'mode': {'type': lambda x: int(x, 8), 'default': napkin.helpers.octal('644')},
        'content': {},
        'recurse': {'type': bool, 'default': False},
        'replace': {'type': bool, 'default': True},
        'encoding': {'default': 'utf-8'},
    }
    def write(self, f, s):
        if hasattr(self, 'filter'):
            self.filter(f, s, self)
        else:
            f.write(s)
    def ensure_present(self):
        d = os.path.dirname(self.dest)
        if not os.path.exists(d):
            os.makedirs(d, napkin.helpers.octal('755'))
        n = os.path.basename(self.dest)
        (fd, self.tmpname) = tempfile.mkstemp('', '.' + n + '.', d)
        os.close(fd)
        f = open(self.tmpname, 'wb')
        if hasattr(self, "content"):
            self.write(f, self.content.encode(self.encoding))
        elif hasattr(self, "source"):
            napkin.helpers.file_fetcher(self.source, lambda x: self.write(f, x))
        f.close()
        os.chmod(self.tmpname, self.mode)
        if hasattr(self, 'owner') or hasattr(self, 'group'):
            uid = -1
            gid = -1
            if hasattr(self, 'owner'):
                try:
                    uid = int(self.owner)
                except:
                    pass
                try:
                    uid = pwd.getpwnam(self.owner).pw_uid
                except:
                    raise ValueError("unable to map owner %s" % self.owner)
            if hasattr(self, 'group'):
                try:
                    gid = int(self.group)
                except:
                    pass
                try:
                    gid = grp.getgrnam(self.group).gr_gid
                except:
                    raise ValueError("unable to map group %s" % self.group)
            os.chown(self.tmpname, uid, gid)
        if napkin.helpers.files_differ(self.tmpname, self.dest):
            if os.path.lexists(self.dest):
                os.unlink(self.dest)
                self.notify_subscribers('update')
            else:
                self.notify_subscribers('create')
            os.rename(self.tmpname, self.dest)
            self.success = True
            return "%s updated" % self.dest
        else:
            os.unlink(self.tmpname)
            self.success = True
            return "%s unmodified" % self.dest
    def ensure_absent(self):
        if os.path.lexists(self.dest):
            os.unlink(self.dest)
            self.notify_subscribers('remove')
            self.success = True
            return "%s removed" % self.dest
        else:
            self.success = True
    def post(self):
        if hasattr(self, 'tmpname') and os.path.lexists(self.tmpname):
            os.unlink(self.tmpname)

class m_df(napkin.monitor):
    properties = {
    }
    def fetch(self):
        stats = os.statvfs(self.name)
        ret = {'free': stats.f_bsize * stats.f_bfree,
               'avail': stats.f_bsize * stats.f_bavail,
               'size': stats.f_bsize * stats.f_blocks}
        return ret

class m_shell(napkin.monitor):
    def_name = 'command'
    properties = {
        'command': {'required': True},
    }
    def fetch(self):
        p = subprocess.Popen(self.command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate()
        if p.returncode != 0:
            raise napkin.MonitoringException(self, p.returncode, "%s failed: %d %s" % (self.name, p.returncode, stderr))
        return 0

class m_shell_out(napkin.monitor):
    def_name = 'command'
    properties = {
        'command': {'required': True},
    }
    def fetch(self):
        p = subprocess.Popen(self.command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate()
        return int(stdout.strip())

class t_exec(napkin.resource):
    def_name = 'command'
    properties = {
        'command': {'required': True},
    }
    def ensure_present(self):
        p = subprocess.Popen(self.command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate()
        if p.returncode != 0:
            return "%s: failed: %d: %s" % (self.name, p.returncode, stderr)
        else:
            self.success = True
            return stdout
