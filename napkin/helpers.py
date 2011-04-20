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
import errno
import logging
import napkin.api

logger = logging.getLogger("napkin.helpers")

class FetchException(Exception):
    def __init__(self, url, status, msg):
        Exception.__init__(self, "%s failed with %d %s" % (url, status, msg))
        logger.debug("FetchException: %s, %s, %s" % (url, status, msg))

def get_connection(url, options):
    up = napkin.api.urlparse(url)
    if up.scheme == 'http':
        c = napkin.api.HTTPConnection(up.netloc)
    elif up.scheme == 'https':
        kwargs = {}
        if options:
            if options.cacert and os.path.exists(options.cacert):
                kwargs['ca_certs'] = options.cacert
                kwargs['cert_reqs'] = napkin.api.CERT_REQ
            if options.cert and os.path.exists(options.cert):
                kwargs['certfile'] = options.cert
                if options.key and os.path.exists(options.key):
                    kwargs['keyfile'] = options.key
        c = napkin.api.SecureHTTPConnection(up.netloc, **kwargs)
    else:
        raise TypeError("source %s uses unsupported scheme" % url)
    return (up, c)

def file_fetcher(url, writer, options=None):
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
    elif url.startswith("http://") or url.startswith("https://"):
        (up, c) = get_connection(url, options)
        headers = {'Host': up.netloc}
        c.request("GET", up.path, None, headers)
        resp = c.getresponse()
        if resp.status != 200:
            raise FetchException(url, resp.status, resp.reason)
        length = resp.getheader('Content-Length')
        if length is None:
            raise FetchException(url, resp.status, "no Content-Length")
        while True:
            buf = resp.read(16384)
            if not buf:
                break
            writer(buf)
    else:
        raise TypeError("source %s uses unknown scheme" % url)

def file_sender(url, filename, mimetype=None, options=None):
    (up, c) = get_connection(url, options)
    headers = {'Host': up.netloc}
    if mimetype:
        headers['Content-Type'] = mimetype
    c.request("POST", up.path, open(filename, 'rb'), headers)
    resp = c.getresponse()
    if resp.status != 200:
        raise FetchException(url, resp.status, resp.reason)
    length = None
    try:
        length = int(resp.getheader('content-length', []))
    except:
        raise
    if length is None:
        raise FetchException(url, resp.status, "no Content-Length")
    if length > 4096:
        raise FetchException(url, resp.status, "Content-Length %s too big" % length)
    return resp.read(length)

def octal(v):
    if isinstance(v, int):
        ret = int(0)
        for j in range(1, 32):
            if v == 0:
                break
            p = pow(10, j - 1)
            m = (v % (p * 10)) / p
            v -= p * m
            ret += pow(8, j - 1) * m
        return ret
    else:
        return int(v, 8)

def files_cmp(src, src_st, dst, dst_st):
    import mmap
    f1 = open(src, 'rb')
    f2 = open(dst, 'rb')
    map1 = mmap.mmap(f1.fileno(), src_st.st_size, mmap.MAP_SHARED, mmap.PROT_READ)
    map2 = mmap.mmap(f2.fileno(), dst_st.st_size, mmap.MAP_SHARED, mmap.PROT_READ)
    ret = True
    i = 0
    for i in range(0, int(src_st.st_size / 4096)):
        if map1[i*4096:i*4096+4095] != map2[i*4096:i*4096+4095]:
            ret = False
            break
    if not ret and map1[i*4096:] != map2[i*4096:]:
        ret = False
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
    return not files_cmp(src, src_st, dst, dst_st)

def daemonize(logfile=None, pidfile=None):
    if logfile is None:
        logfile = "/dev/null"
    stdout_log = open(logfile, 'a+')
    stderr_log = open(logfile, 'a+')
    dev_null = open('/dev/null', 'r+')

    os.dup2(stderr_log.fileno(), 2)
    os.dup2(stdout_log.fileno(), 1)
    os.dup2(dev_null.fileno(), 0)
    sys.stderr = stderr_log
    sys.stdout = stdout_log
    sys.stdin = dev_null

    pid = os.fork()
    if pid > 0:
        os._exit(0)
    os.umask(octal('0022'))
    os.setsid()
    os.chdir("/")
    pid = os.fork()
    if pid > 0:
        os._exit(0)

    if pidfile is not None:
        pid = os.getpid()
        pf = open(pidfile, 'w')
        pf.write("%d\n" % pid)
        pf.close()

def to_bytes(s):
    if hasattr(s, 'encode'):
        return s.encode('utf-8')
    elif isinstance(s, bytes):
        return s
    else:
        raise TypeError("object has unknown type %s" % type(s))

if sys.version_info[0] >= 3:
    def execfile(f, g=None, l=None):
        exec(compile(open(f).read(), f, 'exec'), g, l)
else:
    execfile = __builtins__['execfile']
