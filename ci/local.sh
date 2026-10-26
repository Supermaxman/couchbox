#!/bin/sh
# Everything CI checks, in the CI image:  docker run --rm -v "$PWD:/src" -w /src couchbox-dev ci/local.sh
set -eu
ruff check src tests bin/couchbox-firstboot bin/couchbox-updater bin/couchbox-setup bin/couchbox-settings bin/couchbox-frigate
ruff format --check src tests
# shellcheck disable=SC2046  # the list of shell scripts, split on purpose
shellcheck -S warning $(grep -l '^#!/.*sh' bin/* ci/*.sh installer/*.sh image/*.sh system/dracut/90couchbox/*.sh 2>/dev/null)
python3 ci/check_data.py
reuse lint -q || reuse lint
python3 -m pytest -q -p no:cacheprovider
ci/qmllint.sh
ci/screenshots.sh build/shots
echo "all checks passed"
