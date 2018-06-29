#! /usr/bin/env python
"""Performs (incremental) backups of activities for a given Garmin Connect
account.
The activities are stored in a local directory on the user's computer.
The backups are incremental, meaning that only activities that aren't already
stored in the backup directory will be downloaded.
"""
from garminexport.garminbackup import parse_args, garminbackup


if __name__ == "__main__":

    args = parse_args()
    garminbackup(args=args)
