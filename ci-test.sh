#!/bin/bash

set -o errexit

python3 -m virtualenv env
. ./env/bin/activate || . ./env/Scripts/activate
git config user.name "test user"
make requirements
make lint
make test
