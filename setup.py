# -*- coding: utf-8 -*-
from setuptools import find_packages, setup

setup(
    name="TracWikiSync",
    version="0.1",
    packages=find_packages(exclude=["*.tests*"]),
    package_data={
        "wikisync": ["templates/*.html"]
    },
    entry_points={
        "trac.plugins": ["wikisync = wikisync"]
    }
)