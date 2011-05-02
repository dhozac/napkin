#!/usr/bin/python -tt
# vim:set ts=4 sw=4 expandtab:
# 
# napkin - database interfaces
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

import logging

logger = logging.getLogger("napkin.db")

conn = None

def connect(**kwargs):
    global conn
    lib = kwargs['provider']
    del kwargs['provider']
    x = __import__(lib, globals(), globals(), [], -1)
    conn = x.connect(**kwargs)
    return conn

def cursor():
    return conn.cursor()

def close():
    return conn.close()

def rollback():
    return conn.rollback()

def commit():
    return conn.commit()

def esc(s):
    # FIXME
    return s.replace("\\", "\\\\").replace("'", "\\'")
