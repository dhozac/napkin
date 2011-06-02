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

class f_base:
    def __init__(self, *args, **kwargs):
        if len(args) > 0 and isinstance(args[0], dict):
            self.kwargs = args[0]
        else:
            self.kwargs = kwargs
    def __str__(self):
        return self.__repr__()
    def __repr__(self):
        ret = self.__class__.__name__ + "("
        ret += repr(self.kwargs)
        ret += ")"
        return ret

class f_simple_template(f_base):
    def __init__(self, *args, **kwargs):
        f_base.__init__(self, *args, **kwargs)
        self.in_at = False
        self.start_char = self.kwargs.get('START', '@')
        self.end_char = self.kwargs.get('END', '@')
    def __call__(self, stream, string, obj):
        s = string.decode(obj.encoding)
        while s:
            if self.in_at:
                end = s.find(self.end_char)
                if end != -1:
                    at = self.at_buf + s[:end]
                    s = s[end + 1:]
                    self.in_at = False
                else:
                    self.at_buf += s
                    break
            else:
                begin = s.find(self.start_char)
                if begin == -1:
                    stream.write(s.encode(obj.encoding))
                    break
                stream.write(s[:begin].encode(obj.encoding))
                s = s[begin + 1:]
                end = s.find(self.end_char)
                if end == -1:
                    self.in_at = True
                    self.at_buf = s
                    break
                at = s[:end]
                s = s[end + 1:]
            if not self.in_at:
                replacement = self.kwargs.get(at, self.start_char + at + self.end_char)
                stream.write(replacement.encode(obj.encoding))
