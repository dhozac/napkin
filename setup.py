#!/usr/bin/python -tt
# vim:set ts=4 expandtab sw=4:

from distutils.core import setup
from distutils.cmd import Command
from distutils.command.sdist import sdist
from distutils.command.install_scripts import install_scripts
import os
import sys

sysconfdir = "/etc"
localstatedir = "/var"
pkgconfdir = "/etc/napkin"
pkgstatedir = "/var/lib/napkin"
sbindir = "/usr/sbin"

data_files = []
for (root, dirs, files) in os.walk("etc"):
    filelist = []
    for fn in files:
        if fn.startswith("."):
            continue
        if fn.endswith(".orig") or fn.endswith("~"):
            continue
        full = os.path.join(root, fn)
        if not os.path.isfile(full):
            continue
        filelist.append(full)

    data_files.append((os.path.join(pkgconfdir, root[4:]), filelist))

    i = 0
    while i < len(dirs):
        if dirs[i].startswith("."):
            del dirs[i]
        else:
            i += 1

extra_dist = ['napkin.spec', 'COPYING', 'Makefile']

class my_sdist(sdist):
    def add_defaults(self):
        sdist.add_defaults(self)
        if self.distribution.has_data_files():
            for data in self.distribution.data_files:
                self.filelist.extend(data[1])
        self.filelist.extend(extra_dist)

class bdist_rpmspec(Command):
    user_options = [("rpmdef=", None, "define variables")]
    def initialize_options(self):
        self.rpmdef = None
    def finalize_options(self):
        pass
    def run(self):
        saved_dist_files = self.distribution.dist_files[:]
        sdist = self.reinitialize_command('sdist')
        sdist.formats = ['gztar']
        self.run_command('sdist')
        self.distribution.dist_files = saved_dist_files
        command = ["rpmbuild", "-tb"]
        if self.rpmdef is not None:
            command.extend(["--define", self.rpmdef])
        command.append(sdist.get_archive_files()[0])
        print("running '%s'" % "' '".join(command))
        if not self.dry_run:
            os.spawnvp(os.P_WAIT, "rpmbuild", command)

class my_install_scripts(install_scripts):
    def run(self):
        self.mkpath(self.install_dir)
        for i in os.listdir(self.build_dir):
            srcname = os.path.join(self.build_dir, i)
            dstname = os.path.join(self.install_dir, i)
            if dstname.endswith(".py"):
                dstname = dstname[:-3]
            self.copy_file(srcname, dstname)
            self.outfiles.append(dstname)

# FIXME: there has to be a better way to do this.
if sys.argv[1] == "install":
    args = [sys.argv[1], "--install-scripts=%s" % sbindir] + sys.argv[2:]
else:
    args = sys.argv[1:]

setup(name='napkin',
      version='0.1',
      description='Configuration management and monitoring system',
      url='http://github.com/dhozac/napkin',
      license='GPLv3',
      author='Daniel Hokka Zakrisson',
      author_email='daniel@hozac.com',
      packages=['napkin'],
      data_files=data_files,
      script_args=args,
      scripts=['agent/napkind.py', 'master/napkin-master.py'],
      cmdclass={'sdist': my_sdist, 'bdist_rpmspec': bdist_rpmspec, 'install_scripts': my_install_scripts},
     )
