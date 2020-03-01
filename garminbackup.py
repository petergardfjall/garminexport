#! /usr/bin/env python
"""This python script calls garminexport.garminbackup module with CLI parsed arguments
and performs (incremental) backups of activities for a given Garmin Connect account.
The activities are stored in a local directory on the user's computer.
The backups are incremental, meaning that only activities that aren't already
stored in the backup directory will be downloaded.
"""
import logging

from garminexport.cli import parse_args
from garminexport.garminbackup import garminbackup

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s [%(levelname)s] %(message)s")

if __name__ == "__main__":
    garminbackup(args=parse_args())
