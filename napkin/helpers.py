#!/usr/bin/python -tt
# vim:set ts=4 sw=4 expandtab:
# 
# napkin - helper functions for common tasks
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
import subprocess
import errno

def file_fetcher(url, writer):
    if url.startswith("/") or url.startswith("file://"):
        if url.startswith("file://"):
            url = url[7:]
        f = open(url, 'r')
        while True:
            buf = f.readline(4096)
            if not buf:
                break
            writer(buf)
        f.close()
    elif url.startswith("http://") or url.startswith("https://") or url.startswith("ftp://"):
        p = subprocess.Popen(["curl", "-s", "-S", "-L", "-f", url], stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        while True:
            buf = p.stdout.readline(4096)
            if not buf:
                break
            writer(buf)
        ret = p.wait()
        if ret != 0:
            raise Exception("unable to execute curl: %d" % ret)
    else:
        raise TypeError("source %s uses unknown scheme" % url)

def octal(i):
    return int(i, 8)

def files_cmp(src, src_st, dst, dst_st):
    import mmap
    f1 = open(src, 'rb')
    f2 = open(dst, 'rb')
    map1 = mmap.mmap(f1.fileno(), src_st.st_size, mmap.MAP_SHARED, mmap.PROT_READ)
    map2 = mmap.mmap(f2.fileno(), dst_st.st_size, mmap.MAP_SHARED, mmap.PROT_READ)
    ret = False
    i = 0
    for i in range(0, int(src_st.st_size / 4096)):
        if map1[i*4096:i*4096+4095] != map2[i*4096:i*4096+4095]:
            ret = True
            break
    if not ret and map1[i*4096:] != map2[i*4096:]:
        ret = True
    map1.close()
    map2.close()
    f1.close()
    f2.close()
    return ret

def files_differ(src, dst):
    try:
        dst_st = os.stat(dst)
    except OSError:
        if sys.exc_info()[1].errno == errno.ENOENT:
            return True
        else:
            raise
    try:
        src_st = os.stat(src)
    except OSError:
        if sys.exc_info()[1].errno == errno.ENOENT:
            return True
        else:
            raise
    for i in ['st_size', 'st_mode', 'st_uid', 'st_gid']:
        if getattr(dst_st, i) != getattr(src_st, i):
            return True
    return files_cmp(src, src_st, dst, dst_st)

if sys.version_info[0] >= 3:
    def execfile(f, g=None, l=None):
        exec(compile(open(f).read(), f, 'exec'), g, l)
else:
    execfile = __builtins__['execfile']
