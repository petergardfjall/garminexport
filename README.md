![Build badge](https://github.com/petergardfjall/garminexport/actions/workflows/run-tests.yaml/badge.svg)
[![PyPi release](https://img.shields.io/pypi/v/garminexport.svg)](https://img.shields.io/pypi/v/garminexport.svg)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/garminexport)
![PyPI - License](https://img.shields.io/pypi/l/garminexport)

# About

`garminexport` is both a library and a tool for downloading/backing up [Garmin
Connect](http://connect.garmin.com/) activities to a local disk.

The main utility script is called `garmin-backup` and performs incremental
backups of your Garmin account to a local directory. The first time
`garmin-backup` is run, it will download *all* activities. After that, it will
do incremental backups of your account. That is, the script will only download
activities that haven't already been downloaded to the backup directory.


# Installation

`garminexport` is available on [PyPi](https://pypi.org/) and can be installed
with [pip](http://pip.readthedocs.org):

``` bash
pip install garminexport
```

To install `garminexport` with support to circumvent Cloudflare's bot protection
(which has been known to impact some users) you can install the module with the
`cloudflare`
[extra](https://setuptools.pypa.io/en/latest/userguide/dependency_management.html#optional-dependencies) like so:

``` bash
pip install garminexport[cloudflare]
```

This replaces the default [requests](https://github.com/psf/requests) library
with [cloudscraper](https://github.com/VeNoMouS/cloudscraper) for HTTP request.

# Usage

## Prerequisites
To be of any use you need to register an account at [Garmin
Connect](http://connect.garmin.com/) and populate it with some activities.


## As a command-line tool (garmin-backup)

The backup program is run as follows (use the `--help` flag for a full list of
available options):

``` bash
garmin-backup --backup-dir=activities <username or email>
```

Once started, the program will prompt you for your account password and then log
in to your Garmin Connect account to download activities to the specified backup
directory on your machine. The program will only download activities that aren't
already in the backup directory.

Activities can be exported in any of the formats outlined below. Note that
by default, the program downloads all formats for every activity. Use the
`--format` option to narrow the selection.

Supported export formats:


  -   `gpx`: activity GPX file (XML).

      <sub>[GPX](https://en.wikipedia.org/wiki/GPS_Exchange_Format) is an open
      format, mainly for storing GPS routes/tracks. It does support extensions
      and Garmin appears to annotate the GPS data with, for example, heart-rate
      and cadence, when available on your device.</sub>

  -   `tcx`: an activity TCX file (XML).
      *Note: a `.tcx` file may not always be possible to export, for example
      if an activity was uploaded in gpx format. In that case, Garmin won't try
      to synthesize a tcx file.*

      <sub>[TCX](https://en.wikipedia.org/wiki/Training_Center_XML) (Training
      Center XML) is Garmin's own XML format. It is, essentially, an extension
      of GPX which includes more metrics and divides the GPS track into "laps"
      as recorded by your device (with "lap summaries" for each metric).</sub>

  -   `fit`: activity FIT file (binary format).
      *Note: a `.fit` file may not always be possible to export, for example
      if an activity was entered manually rather than imported from a Garmin device.*

      <sub>The [FIT](https://www.thisisant.com/resources/fit/) format is the
      "raw data type" stored in your Garmin device and should contain all
      metrics your device is capable of tracking (GPS, heart rate, cadence,
      etc). It's a binary format, so tools are needed to read its content.</sub>

  -   `json_summary`: activity summary file (JSON).

      <sub>Provides summary data for an activity. Seems to lack a formal schema
      and should not be counted on as a stable data format (it may change at any
      time). Only included since it *may* contain additional data that could be
      useful for developers of analysis tools.</sub>

  -   `json_details`: activity details file (JSON).

      <sub>Provides detailed activity data in a JSON format. Seems to lack a
      formal schema and should not be counted on as a stable data format (it may
      change at any time). Only included since it *may* contain additional data
      that could be useful for developers of analysis tools.</sub>

All files are written to the same directory (`activities/` by default).  Each
activity file is prefixed by its upload timestamp and its activity id.

`garminexport` also contains a few smaller utility programs:

- `garmin-get-activity`: download a single Garmin Connect activity. Run with
  `--help`for more details.
- `garmin-upload-activity`: uplad a single Garmin Connect activity file (`.fit`,
  `.gpx`, or `.tcx`). Run with `--help`for more details.

## As a library

To build your own tools around the Garmin Connect API you can import the
`garminclient` module. It handles authentication to establish a secure session
with Garmin Connect. For example use, have a look at the command-line tools
under [garminexport/cli](garminexport/cli).

For example, in your `setup.py`, `setup.cfg`, `pyproject.toml` ([PEP
631](https://peps.python.org/pep-0631/)) add something like:

``` python
install_requires=[
    'garminexport',
    # also installs 'cloudscraper' as a dependency
    # 'garminexport[cloudflare]',
    ...
]
```

Note: if you happen to have
[cloudscraper](https://github.com/VeNoMouS/cloudscraper) on your `PACKAGEPATH`
`GarminClient` will make use of it whenever it needs to make an HTTP request.

# Contribute

To start working on the code, create a virtual environment (an isolated
development environment) and install the required dependencies like so:

    # create virtualenv and populate it with library dependencies
    make dev-init

    # activate virtualenv
    source .venv/bin/activate

    # code ...

    # test
    make test
