garminexport
============
``garminexport.py`` is a program that downloads *all* 
activities for a given [Garmin Connect](http://connect.garmin.com/) 
account and stores them locally on the user's computer.

The directory also contains an ``incremental_backup.py`` program that can be
used for incremental backups of your account. This script only downloads
activities that haven't already been downloaded to a certain backup directory.
It is typically a quicker alternative (except for the first time when all
activities will need to be downloaded).


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


Running the export program
==========================
The export program is run as follows (use the ``--help`` flag for a list of
available options).

    ./garminexport.py <username or email>

Once started, the program will prompt you for your account password and then
log in to your Garmin Connect account to download *all* activities to a 
destination directory on your machine.

For each activity, these files are stored: 

  -   an activity summary file (JSON)
    
  -   an activity details file (JSON)

  -   an activity GPX file (XML)

  -   an activity TCX file (XML)

  -   an activity FIT file (binary) (if available -- the activity may have
      been entered manually rather than imported from a Garmin device).

All files are written to the same directory (``activities/`` by default).
Each activity file is prefixed by its upload timestamp and its 
activity id.


Running the incremental backup program
======================================
The incremental backup program is run in a similar fashion to the export 
program (use the ``--help`` flag for a list of available options):

    ./incremental_backup.py --backup-dir=activities <username or email>

In this example, it will only download activities that aren't already in
the ``activities/`` directory. Note: The incremental backup program saves
the same files for each activity as the export program (see above).


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
