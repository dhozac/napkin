#!/usr/bin/python -tt
# vim:set ts=4 sw=4 expandtab:
# 
# napkin - selects providers based on the current system
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

providers = []

def load(reqprov=None):
    if reqprov is None:
        if not providers:
            import napkin.providers.filters
            providers.append('filters')

            if os.name == 'posix':
                import napkin.providers.posix
                providers.append('posix')

            if os.uname()[0] == 'Linux':
                import napkin.providers.linux
                providers.append('linux')

            if (os.path.exists("/etc/fedora-release") or
                os.path.exists("/etc/redhat-release") or
                os.path.exists("/etc/centos-release")):
                import napkin.providers.redhat
                providers.append('redhat')

        reqprov = providers
    else:
        for i in reqprov:
            m = __import__("napkin.providers.%s" % i, globals(), locals(), [], -1)

    ret = {}
    for i in reqprov:
        m = sys.modules["napkin.providers.%s" % i]
        for j in dir(m):
            if j.startswith("t_") or j.startswith("m_") or j.startswith("f_"):
                ret[j] = getattr(m, j)
    return ret
