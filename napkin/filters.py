#!/usr/bin/python -tt
# vim:set ts=4 sw=4 expandtab:
# 
# napkin - filters for templating and common configuration files
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

import re
import logging

class f_apache:
    def __init__(self, *args, **kwargs):
        if len(args) > 0 and isinstance(args[0], dict):
            self.kwargs = args[0]
        else:
            self.kwargs = kwargs
        self.section = []
    def __call__(self, stream, string, obj):
        stream.write(self.parse(str(string)).encode(obj.encoding))
    def parse(self, s):
        if re.match(r"^\s*#", s):
            return s
        m = re.match(r"^\s*<(/?)([A-Za-z0-9_]+)(\s+(.*))?>(\r?\n?)", s)
        if m is not None:
            if m.group(1) == "/":
                self.section = self.section[:-1]
            else:
                arg = m.group(4).replace('"', "").replace("'", "")
                self.section.append((m.group(2), arg))
            return s
        else:
            m = re.match(r"^(\s*)([A-Za-z0-9_]+)(\s+).*(\r?\n?)", s)
            if not m:
                return s
            name = ""
            for i in self.section:
                name += "%s=%s/" % (i[0], i[1])
            name += m.group(2)
            if name in self.kwargs:
                return m.group(1) + m.group(2) + m.group(3) + self.kwargs[name] + m.group(4)
            else:
                return s
