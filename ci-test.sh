#!/bin/bash

set -o errexit

make env

. ./env/bin/activate || . ./env/Scripts/activate
if [ -n "$CI" ]; then
    git config user.name "test user"
fi

make requirements
make test
