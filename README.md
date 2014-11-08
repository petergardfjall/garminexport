garminexport
============
The Garmin Connect activity exporter is a program that downloads all activities 
for a given [Garmin Connect](http://connect.garmin.com/) account and stores them locally on the user's computer.

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

Run the program
===============
The program is run as follows (use the ``--help`` flag for a list of
available options).

    ./garminexport.py <username or email>

Once started, the program will prompt you for your account password and then
log in to your Garmin Connect account to download all activities to a destination
directory on your machine.

For each activity, three files are stored: an activity summary (JSON),
activity details (JSON) and the activity GPX file. All files are written
to the same directory (``activities/<timestamp>/`` by default).
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
