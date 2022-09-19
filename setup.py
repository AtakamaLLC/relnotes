# SPDX-FileCopyrightText: © Atakama, Inc <support@atakama.com>
# SPDX-License-Identifier: LGPL-3.0-or-later

from setuptools import setup


def long_description():
    from os import path

    this_directory = path.abspath(path.dirname(__file__))
    with open(path.join(this_directory, "README.md")) as readme_f:
        contents = readme_f.read()
        return contents


setup(
    name="relnotes",
    version="1.0.0",
    description="Release notes manager",
    packages=["relnotes"],
    long_description=long_description(),
    long_description_content_type="text/markdown",
    setup_requires=["wheel"],
    entry_points={"console_scripts": ["relnotes=relnotes.main:main"]},
)
