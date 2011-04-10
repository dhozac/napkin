%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%global with_python3 0
%else
%global __python %{__python3}
%global python_sitelib %python3_sitelib
%global with_python3 1
%endif

Name:		napkin
Version:	0.1
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
make install DESTDIR="%{buildroot}" \
	sbindir="%{_sbindir}" \
	initddir="%{_initrddir}" \
	pythondir="%{python_sitelib}" \
	sysconfdir="%{_sysconfdir}"


%clean
rm -rf "%{buildroot}"


%files
%defattr(-,root,root,-)
%doc COPYING
%{python_sitelib}/napkin
%{python_sitelib}/napkin*.egg-info

%files master
%defattr(-,root,root,-)
%{_sbindir}/napkin-master

%files client
%defattr(-,root,root,-)
%{_sbindir}/napkind


%changelog
* Sat Apr 09 2011 Daniel Hokka Zakrisson <daniel@hozac.com> - 0.1-1
- initial release