#!/bin/bash

if [ -n "$CI" ]; then
    git config --global user.name "test user"
fi
make lint
