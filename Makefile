PYTHON := python

VERSION := 0.1

sysconfdir = /etc
pkgconfdir = $(sysconfdir)/napkin
sbindir = /usr/sbin
localstatedir = /var
pkgstatedir = $(localstatedir)/lib/napkin
pythondir := $(shell $(PYTHON) -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")
initddir = $(sysconfdir)/init.d

install:
	# Copy library
	mkdir -p $(DESTDIR)$(pythondir)/napkin $(DESTDIR)$(pythondir)/napkin/providers
	cp -p napkin/*.py $(DESTDIR)$(pythondir)/napkin/
	cp -p napkin/providers/*.py $(DESTDIR)$(pythondir)/napkin/providers
	# Copy programs
	mkdir -p $(DESTDIR)$(sbindir)
	cp -p agent/napkind.py $(DESTDIR)$(sbindir)/napkind
	cp -p master/napkin-master.py $(DESTDIR)$(sbindir)/napkin-master
	# Copy configuration
	mkdir -m 0700 -p $(DESTDIR)$(pkgconfdir)
	cp -p etc/*.conf $(DESTDIR)$(pkgconfdir)
	# Create state directory
	mkdir -m 0700 -p $(DESTDIR)$(pkgstatedir)
	# Install initscripts
	mkdir -p $(DESTDIR)$(initddir)
	cp -p agent/napkind.init $(DESTDIR)$(initddir)/napkind
	cp -p master/napkin-master.init $(DESTDIR)$(initddir)/napkin-master

dist: napkin-$(VERSION).tar.bz2
napkin-$(VERSION).tar.bz2: $(shell git ls-files)
	git archive --format=tar --prefix=napkin-$(VERSION)/ HEAD | bzip2 -9 > napkin-$(VERSION).tar.bz2

rpm: napkin-$(VERSION).tar.bz2
	rpmbuild -tb $<

clean:
	rm -f napkin-$(VERSION).tar.bz2
