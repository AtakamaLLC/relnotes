#!/bin/bash

if [ -n "$CI" ]; then
    git config user.name "test user"
fi
make lint
