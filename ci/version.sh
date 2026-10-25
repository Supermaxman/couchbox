#!/bin/sh
# The version in the source tree (src/couchbox/__init__.py)
sed -n 's/^__version__ = "\([^"]*\)".*/\1/p' "$(dirname "$0")/../src/couchbox/__init__.py"
