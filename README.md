![Build badge](https://github.com/petergardfjall/garminexport/actions/workflows/run-tests.yaml/badge.svg)
[![PyPi release](https://img.shields.io/pypi/v/garminexport.svg)](https://img.shields.io/pypi/v/garminexport.svg)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/garminexport)
![PyPI - License](https://img.shields.io/pypi/l/garminexport)

# About

`garminexport` is both a library and a tool for downloading/backing up
[Garmin Connect](http://connect.garmin.com/) activities to local disk.

The main utility script is called `garmin-backup` and performs incremental
backups of your Garmin account to a local directory. The first time
`garmin-backup` is run, it will download _all_ activities. After that, it will
do incremental backups of your account. That is, the script will only download
activities that haven't already been downloaded to the backup directory.

# Installation

`garminexport` is available on [PyPi](https://pypi.org/) and can be installed
with [pip](http://pip.readthedocs.org):

```bash
pip install garminexport
```

# Usage

## Prerequisites

To be of any use you need to register an account at
[Garmin Connect](http://connect.garmin.com/) and populate it with some
activities.

## Authentication

> [!NOTE]  
> <sub>It has been proposed (e.g. in
> [#102](https://github.com/petergardfjall/garminexport/issues/102)) that
> `garminexport` be migrated to use [garth](https://github.com/matin/garth), a
> library that uses API secrets from the Garmin Connect Android app. Although
> admittedly an approach more suitable for automation, the legal implications of
> using such API secrets without
> [proper permit](https://www.garmin.com/en-US/forms/GarminConnectDeveloperAccess/)
> are unclear.</sub>
>
> <sub>Instead `garminexport` sticks to its original spirit of only doing what a
> human user would rightfully be able to do through the web browser. This does
> come at the price of requiring some manual work.</sub>

Over the years Garmin has made it increasingly difficult to programatically
access their site (without a
[proper permit](https://www.garmin.com/en-US/forms/GarminConnectDeveloperAccess/)
and API keys, which are only handed out to businesses). They have systematically
added bot protection (such as browser detection and CAPTCHAs) to their
authentication flow to prevent scripted access. Trying to keep up with this over
time became unsustainable.

As of version `0.6.0` of `garminexport`, the authentication flow was reworked to
rely on the human user to perform the actual login _through a web-browser_ and
then, via web browser developer tools, extract the tokens needed to authenticate
further client interactions (proposed by @ryeguard in
https://github.com/petergardfjall/garminexport/pull/115).

After logging in at https://connect.garmin.com (using your web browser of
choice) there are two tokens that need to be supplied to `garminexport` for it
to authenticate its client requests:

- A `JWT_FGP` cookie: extract its value through web browser developer tools by
  looking at cookies stored for https://connect.garmin.com.
- An OAuth bearer token: extract its value through web browser developer tools
  by looking at the request (not response) `Headers` of a network request. The
  header to look for is `Authorization` and the the token value is everything
  following the leading `Bearer` string.

## As a command-line tool (garmin-backup)

The backup program is run as follows, with `--bearer-token` and
`--jwt-fgp-cookie` extracted as explained in the section on
[Authentication](#authentication). Use the `--help` flag for a full list of
available options:

```bash
garmin-backup --backup-dir=activities --bearer-token="eyJ[..]Q4g" --jwt-fgp-cookie=5768b018-dda6-4e51-add9-f4b8eb5c1758
```

Once started, the program will prompt you for your account password and then log
in to your Garmin Connect account to download activities to the specified backup
directory on your machine. The program will only download activities that aren't
already in the backup directory.

Activities can be exported in any of the formats outlined below. Note that by
default, the program downloads all formats for every activity. Use the
`--format` option to narrow the selection.

Supported export formats:

- `gpx`: activity GPX file (XML).

  <sub>[GPX](https://en.wikipedia.org/wiki/GPS_Exchange_Format) is an open
  format, mainly for storing GPS routes/tracks. It does support extensions and
  Garmin appears to annotate the GPS data with, for example, heart-rate and
  cadence, when available on your device.</sub>

- `tcx`: an activity TCX file (XML). _Note: a `.tcx` file may not always be
  possible to export, for example if an activity was uploaded in gpx format. In
  that case, Garmin won't try to synthesize a tcx file._

  <sub>[TCX](https://en.wikipedia.org/wiki/Training_Center_XML) (Training Center
  XML) is Garmin's own XML format. It is, essentially, an extension of GPX which
  includes more metrics and divides the GPS track into "laps" as recorded by
  your device (with "lap summaries" for each metric).</sub>

- `fit`: activity FIT file (binary format). _Note: a `.fit` file may not always
  be possible to export, for example if an activity was entered manually rather
  than imported from a Garmin device._

  <sub>The [FIT](https://www.thisisant.com/resources/fit/) format is the "raw
  data type" stored in your Garmin device and should contain all metrics your
  device is capable of tracking (GPS, heart rate, cadence, etc). It's a binary
  format, so tools are needed to read its content.</sub>

- `json_summary`: activity summary file (JSON).

  <sub>Provides summary data for an activity. Seems to lack a formal schema and
  should not be counted on as a stable data format (it may change at any time).
  Only included since it _may_ contain additional data that could be useful for
  developers of analysis tools.</sub>

- `json_details`: activity details file (JSON).

  <sub>Provides detailed activity data in a JSON format. Seems to lack a formal
  schema and should not be counted on as a stable data format (it may change at
  any time). Only included since it _may_ contain additional data that could be
  useful for developers of analysis tools.</sub>

All files are written to the same directory (`activities/` by default). Each
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

For example, in your `setup.py`, `setup.cfg`, `pyproject.toml`
([PEP 631](https://peps.python.org/pep-0631/)) add something like:

```python
install_requires=[
    'garminexport',
    ...
]
```

# Contribute

To start working on the code, create a virtual environment (an isolated
development environment) and install the required dependencies like so:

    # create virtualenv and populate it with library dependencies
    make dev-init

    # activate virtualenv
    source .venv/bin/activate

    # test
    make test
