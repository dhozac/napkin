%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%global with_python3 0
%else
%global __python %{__python3}
%global python_sitelib %python3_sitelib
%global with_python3 1
%endif

Name:		napkin
Version:	0.1.2
Release:	1%{?dist}
Summary:	Configuration management and monitoring system

Group:		System Environment/Daemons
License:	GPLv3
URL:		http://github.com/dhozac/napkin
Source0:	napkin-%{version}.tar.bz2
BuildRoot:	%(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)

BuildArch:	noarch

%if %with_python3
BuildRequires:	python3-devel
%else
BuildRequires:	python2-devel
%endif

%description
Configures and monitors systems.

%package master
Summary:	Controls a napkin network
Group:		System Environment/Daemons
Requires:	napkin = %{version}-%{release}

%description master
Controls a napkin network.

%package client
Summary:	Configures a napkin node
Group:		System Environment/Daemons
Requires:	napkin = %{version}-%{release}

%description client
Configures a napkin node.

%prep
%setup -q


%build


%install
rm -rf "%{buildroot}"
%{__python} setup.py install --destdir="%{buildroot}" \
	--prefix="%{_prefix}" \
	--sbindir="%{_sbindir}" \
	--initddir="%{_initrddir}" \
	--sysconfdir="%{_sysconfdir}"


%clean
rm -rf "%{buildroot}"


%files
%defattr(-,root,root,-)
%doc COPYING
%dir %{_sysconfdir}/napkin
%config(noreplace) %{_sysconfdir}/napkin/*-template.ct
%config(noreplace) %{_sysconfdir}/napkin/logging.conf
%{python_sitelib}/napkin

%files master
%defattr(-,root,root,-)
%config(noreplace) %{_sysconfdir}/napkin/master.conf
%{_initrddir}/napkin-master
%{_sbindir}/napkin-master
%{_sbindir}/napkin-run
%{_sbindir}/napkin-ca

%files client
%defattr(-,root,root,-)
%{_initrddir}/napkind
%{_sbindir}/napkind


%changelog
* Sat Apr 09 2011 Daniel Hokka Zakrisson <daniel@hozac.com> - 0.1-1
- initial release
