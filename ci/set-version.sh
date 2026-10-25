#!/bin/sh
# Stamp a version into the package: ci/set-version.sh 0.2.0 (or 0.2.0-beta.1)
set -eu
v=${1#v}
sed -i "s/^__version__ = \"[^\"]*\"/__version__ = \"$v\"/" src/couchbox/__init__.py
deb=$(printf '%s' "$v" | sed 's/-/~/')          # 0.2.0-beta.1 -> 0.2.0~beta.1 (sorts before 0.2.0)
if ! head -1 debian/changelog | grep -q "($deb)"; then
  { printf 'couchbox (%s) unstable; urgency=medium\n\n  * Release %s: see CHANGELOG.md.\n\n -- Couchbox Authors <couchbox@users.noreply.github.com>  %s\n\n' \
      "$deb" "$v" "$(date -R)"; cat debian/changelog; } > debian/changelog.new
  mv debian/changelog.new debian/changelog
fi
echo "version $v (deb $deb)"
