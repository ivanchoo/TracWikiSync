# -*- coding: utf-8 -*-
from setuptools import find_packages, setup

setup(
    name="TracWikiSync",
    version="0.3",
    keywords="trac wiki sync synchronization",
    author="Ivan Choo",
    author_email="hello@ivanchoo.com",
    url="https://github.com/ivanchoo/TracWikiSync",
    description="Synchronize wiki entries between to separate Trac installations",
    packages=find_packages(exclude=["*.tests*"]),
    package_data={
        "wikisync": [
            "templates/*.html", 
            "htdocs/*.*",
            "htdocs/images/*.*"
        ]
    },
    entry_points={
        "trac.plugins": ["wikisync=wikisync"]
    }
)