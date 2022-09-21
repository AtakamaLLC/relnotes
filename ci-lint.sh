#!/bin/bash -e

set -o errexit

if [ -n "$CI" ]; then
    git config --global user.name "test user"
fi

make lint

if [ -n "$GITHUB_BASE_REF" ]; then
    # only check when merging
    git fetch origin master
    make check-notes
fi
