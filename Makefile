PYTHON := /usr/bin/python

VERSION := 0.1

prefix := /usr
sysconfdir := $(prefix)/etc
pkgconfdir := $(sysconfdir)/napkin
sbindir := $(prefix)/sbin
localstatedir := $(prefix)/var
pkgstatedir := $(localstatedir)/lib/napkin
pythondir := $(shell $(PYTHON) -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")
initddir := $(sysconfdir)/init.d

all:

install: install-lib install-master install-agent

install-lib:
	mkdir -p $(DESTDIR)$(pythondir)/napkin $(DESTDIR)$(pythondir)/napkin/providers
	install -p -m 644 napkin/*.py $(DESTDIR)$(pythondir)/napkin/
	install -p -m 644 napkin/providers/*.py $(DESTDIR)$(pythondir)/napkin/providers/

install-master: install-lib
	mkdir -p $(DESTDIR)$(sbindir)
	for i in master/napkin-master.py master/napkin-ca.py; do \
		n=$${i##*/}; n=$${n%.py}; \
		sed -e 's:^#!.*:#!$(PYTHON) -tt:' $$i > $(DESTDIR)$(sbindir)/$$n; \
		touch -r $$i $(DESTDIR)$(sbindir)/$$n; \
		chmod --reference=$$i $(DESTDIR)$(sbindir)/$$n; \
	done
	mkdir -m 0700 -p $(DESTDIR)$(pkgconfdir)
	@for i in etc/master.conf; do \
		if test ! -e $(DESTDIR)$(pkgconfdir)/`basename $$i`; then \
			echo install -p -m 644 $$i $(DESTDIR)$(pkgconfdir); \
			install -p -m 644 $$i $(DESTDIR)$(pkgconfdir); \
		fi; done
	mkdir -p $(DESTDIR)$(initddir)
	install -p -m 755 master/napkin-master.init $(DESTDIR)$(initddir)/napkin-master

install-agent: install-lib
	mkdir -p $(DESTDIR)$(sbindir)
	sed -e 's:^#!.*:#!$(PYTHON) -tt:' agent/napkind.py > $(DESTDIR)$(sbindir)/napkind
	touch -r agent/napkind.py $(DESTDIR)$(sbindir)/napkind
	chmod --reference=agent/napkind.py $(DESTDIR)$(sbindir)/napkind
	mkdir -m 0700 -p $(DESTDIR)$(pkgconfdir)
	@for i in etc/logging.conf etc/template.ct; do \
		if test ! -e $(DESTDIR)$(pkgconfdir)/`basename $$i`; then \
			echo install -p -m 644 $$i $(DESTDIR)$(pkgconfdir); \
			install -p -m 644 $$i $(DESTDIR)$(pkgconfdir); \
		fi; done
	mkdir -m 0700 -p $(DESTDIR)$(pkgstatedir)
	mkdir -p $(DESTDIR)$(initddir)
	install -p -m 755 agent/napkind.init $(DESTDIR)$(initddir)/napkind

dist: napkin-$(VERSION).tar.bz2
napkin-$(VERSION).tar.bz2: $(shell git ls-files)
	git archive --format=tar --prefix=napkin-$(VERSION)/ HEAD | bzip2 -9 > napkin-$(VERSION).tar.bz2

rpm: napkin-$(VERSION).tar.bz2
	rpmbuild -tb $<

clean:
	rm -f napkin-$(VERSION).tar.bz2
