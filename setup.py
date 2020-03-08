#!/usr/bin/env python

"""Setup information for the Garmin Connect activity exporter."""

from setuptools import find_packages
from distutils.core import setup

setup(name="Garmin Connect activity exporter",
      version="1.0.0",
      description=("A program that downloads all activities for a given Garmin Connect account "
                   "and stores them locally on the user's computer."),
      long_description=open('README.md').read(),
      author="Peter Gardfjäll",
      author_email="peter.gardfjall.work@gmail.com",
      install_requires=open('requirements.txt').read(),
      license=open('LICENSE').read(),
      url="https://github.com/petergardfjall/garminexport",
      packages=["garminexport"],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'Intended Audience :: End Users/Desktop'
          'Natural Language :: English',
          'License :: OSI Approved :: Apache Software License',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.5+',
      ])
