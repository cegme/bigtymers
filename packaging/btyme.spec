Name:           btyme
Version:        %{btyme_version}
Release:        1
Summary:        Full screen analog and digital clock and countdown timer
License:        MIT
URL:            https://ceg.me/bigtymers
Source0:        bigtymers.py
Source1:        LICENSE
BuildArch:      noarch
Requires:       python3
Requires:       tzdata

%description
BigTymers shows the current time or the time left in a countdown timer
in the terminal, with analog and digital faces, time zones and a
flashing alarm. Made for exams and presentations.
It needs Python 3.9 or newer.

%prep
cp %{SOURCE1} LICENSE

%build

%install
install -D -m 0755 %{SOURCE0} %{buildroot}%{_bindir}/btyme

%files
%license LICENSE
%{_bindir}/btyme

%changelog
* Tue Nov 17 2026 Christan Grant - %{btyme_version}-1
- Release %{btyme_version}
