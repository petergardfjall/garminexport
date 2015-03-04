Garmin Connect activity backup tool
===================================
``garminbackup.py`` is a program that downloads activities for a 
given [Garmin Connect](http://connect.garmin.com/) account and stores 
them in a backup directory locally on the user's computer. The first time 
the program is run, it will download *all* activities. After that, it will
do incremental backups of your account. That is, the script will only download
activities that haven't already been downloaded to the backup directory.

The library contains a simple utility program, ``get_activity.py`` for 
downloading a single Garmin Connect activity. Run ``./get_activity.py --help``
for more details.

The library also contains a ``garminclient`` module that could be used by third-party
projects that need to communicate over the Garmin Connect API. See the 
Library Import section below for more details.


Prerequisites
=============
The instructions below for running the program (or importing the module)
assumes that you have [Python 2.7](https://www.python.org/download/releases/2.7/),
[pip](http://pip.readthedocs.org/en/latest/installing.html), and [virtualenv](http://virtualenv.readthedocs.org/en/latest/virtualenv.html#installation) installed.

It also assumes that you have registered an account at 
[Garmin Connect](http://connect.garmin.com/).


Getting started
===============
Create and activate a new virtual environment to create an isolated development
environment (that contains the required dependencies and nothing else).

    virtualenv venv.garminexport
    . venv.garminexport/bin/activate

Install the required dependencies in this virtual environment:

    pip install -r requirements.txt



Running
=======
The backup program is run as follows (use the ``--help`` flag for a full list 
of available options):

    ./garminbackup.py --backup-dir=activities <username or email>

Once started, the program will prompt you for your account password and then
log in to your Garmin Connect account to download activities to the specified
backup directory on your machine. The program will only download activities 
that aren't already in the backup directory.

Activities can be exported in any of the formats outlined below. Note that
by default, the program downloads all formats for every activity. Use the
``--format`` option to narrow the selection.

Supported export formats:

  -   ``json_summary``: activity summary file (JSON)
    
  -   ``json_details``: activity details file (JSON)

  -   ``gpx``: activity GPX file (XML)

  -   ``tcx``: an activity TCX file (XML).
      *Note: a ``.tcx`` file may not always be possible to export, for example
      if an activity was uploaded in gpx format. In that case, Garmin won't try
      to synthesize a tcx file.*

  -   ``fit``: activity FIT file (binary format).
      *Note: a ``.fit`` file may not always be possible to export, for example
      if an activity was entered manually rather than imported from a Garmin device.*

All files are written to the same directory (``activities/`` by default).
Each activity file is prefixed by its upload timestamp and its activity id.



Library import
==============
To install the development version of this library in your local Python 
environment, run:

  `pip install -e git://github.com/petergardfjall/garminexport.git#egg=garminexport`

or if you prefer to use a `requirements.txt` file, add the following line
to your list of dependencies:

  `-e -e git://github.com/petergardfjall/garminexport.git#egg=garminexport`

and run pip with you dependency file as input:

  `pip install -r requirements.txt`
