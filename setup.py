#!/usr/bin/python
# vim:set ts=4 sw=4 expandtab:

import os
import sys
import shutil
import optparse
import errno
import glob
import re
from distutils.sysconfig import get_python_lib

import napkin.version

parser = optparse.OptionParser(version=napkin.version.__version__)
parser.add_option("--prefix", action="store", dest="prefix", default="/usr/local")
parser.add_option("--sysconfdir", action="store", dest="sysconfdir", default="%(prefix)s/etc")
parser.add_option("--pkgconfdir", action="store", dest="pkgconfdir", default="%(sysconfdir)s/napkin")
parser.add_option("--sbindir", action="store", dest="sbindir", default="%(prefix)s/sbin")
parser.add_option("--localstatedir", action="store", dest="localstatedir", default="%(prefix)s/var")
parser.add_option("--pkgstatedir", action="store", dest="pkgstatedir", default="%(localstatedir)s/lib/napkin")
parser.add_option("--initddir", action="store", dest="initddir", default="%(sysconfdir)s/init.d")
parser.add_option("--destdir", action="store", dest="destdir", default="")
(options, args) = parser.parse_args(sys.argv[1:])

options.pythondir = get_python_lib()
options.srcdir = os.path.dirname(sys.argv[0])

def get_path(name):
    p = getattr(options, name)
    while '%(' in p:
        p = p % options.__dict__
    return p

def mkdir_p(name, mode='755'):
    try:
        os.makedirs(name, int(mode, 8))
    except OSError:
        if sys.exc_info()[1].errno != errno.EEXIST:
            raise

def j(*args):
    r = ""
    for i in args:
        if len(i) == 0:
            continue
        if i[0] != os.path.sep:
            r += os.path.sep
        r += i
    return r

def install(files, dest, replacements=None, keep=False, mode=None, dbn=None):
    if not replacements:
        replacements = {}
    replacements['#![[:space:]]*[^[:space:]]+python[0-9.]*'] = "#!%s" % sys.executable
    reps = {}
    for i in replacements:
        r = re.compile(i)
        reps[r] = replacements[i]
    replacements = reps
    files = glob.glob(files)
    mkdir_p(dest)
    for sn in files:
        bn = os.path.basename(sn)
        if dbn:
            dn = j(dest, dbn)
        else:
            dn = j(dest, bn)
        if keep and os.path.exists(dn):
            continue
        rf = open(sn, 'r')
        wf = open(dn, 'w')
        while True:
            buf = rf.readline()
            if not buf:
                break
            for i in replacements:
                buf = re.sub(i, replacements[i], buf)
            wf.write(buf)
        wf.close()
        rf.close()
        sst = os.stat(sn)
        os.utime(dn, (sst.st_atime, sst.st_mtime))
        if not mode:
            m = sst.st_mode
        else:
            m = int(mode, 8)
        os.chmod(dn, m)

def install_lib():
    install('napkin/*.py', j(get_path("destdir"), get_path("pythondir"), "napkin"), mode='644')
    install('napkin/providers/*.py', j(get_path("destdir"), get_path("pythondir"), "napkin", "providers"), mode='644')

def install_master():
    install('master/napkin-master.py', j(get_path("destdir"), get_path("sbindir")), mode='755', dbn='napkin-master')
    install('master/napkin-run.py', j(get_path("destdir"), get_path("sbindir")), mode='755', dbn='napkin-run')
    install('master/napkin-ca.py', j(get_path("destdir"), get_path("sbindir")), mode='755', dbn='napkin-ca')
    mkdir_p(j(get_path("destdir"), get_path("pkgconfdir")), '700')
    for i in ['etc/master.conf', 'etc/agent-template.ct', 'etc/master-template.ct']:
        install(i, j(get_path("destdir"), get_path("pkgconfdir")), mode='644', keep=True)
    install('master/napkin-master.init', j(get_path("destdir"), get_path("initddir")), mode='755', dbn='napkin-master')

def install_agent():
    install('agent/napkind.py', j(get_path("destdir"), get_path("sbindir")), mode='755', dbn='napkind')
    mkdir_p(j(get_path("destdir"), get_path("pkgconfdir")), '700')
    for i in ['etc/logging.conf', 'etc/agent-template.ct']:
        install(i, j(get_path("destdir"), get_path("pkgconfdir")), mode='644', keep=True)
    install('agent/napkind.init', j(get_path("destdir"), get_path("initddir")), mode='755', dbn='napkind')
    mkdir_p(j(get_path("destdir"), get_path("pkgstatedir")), '700')

def dist():
    ver = napkin.version.__version__
    ret = os.system("git archive --format=tar --prefix=napkin-%s/ HEAD | bzip2 -9 > napkin-%s.tar.bz2" % (ver, ver))
    if ret != 0:
        raise Exception("creating archive failed with %d" % ret)

def rpm():
    dist()
    ret = os.system("rpmbuild -tb napkin-%s.tar.bz2" % napkin.version.__version__)
    if ret != 0:
        raise Exception("creating RPMs failed with %d" % ret)

if args[0] == "install":
    install_lib()
    install_master()
    install_agent()
elif args[0] == "install-lib":
    install_lib()
elif args[0] == "install-master":
    install_lib()
    install_master()
elif args[0] == "install-agent":
    install_lib()
    install_agent()
elif args[0] == "dist":
    dist()
elif args[0] == "rpm":
    rpm()
else:
    raise Exception("unknown operation %s" % args[0])
