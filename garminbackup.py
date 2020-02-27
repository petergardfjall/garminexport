#! /usr/bin/env python
"""Performs (incremental) backups of activities for a given Garmin Connect
account.
The activities are stored in a local directory on the user's computer.
The backups are incremental, meaning that only activities that aren't already
stored in the backup directory will be downloaded.
"""
import argparse
from datetime import timedelta
import getpass
from garminexport.garminclient import GarminClient
import garminexport.backup
from garminexport.backup import export_formats
from garminexport.retryer import (
    Retryer, ExponentialBackoffDelayStrategy, MaxRetriesStopStrategy)
import logging
import os
import re
import sys
import traceback

logging.basicConfig(
    level=logging.INFO, format="%(asctime)-15s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR
}
"""Command-line (string-based) log-level mapping to logging module levels."""

DEFAULT_MAX_RETRIES = 7
"""The default maximum number of retries to make when fetching a single activity."""

def get_garmin_connect_data(username,password,backup_dir,log_level,format,ignore_errors,max_retries):
    retryer = Retryer(
        delay_strategy=ExponentialBackoffDelayStrategy(
            initial_delay=timedelta(seconds=1)),
        stop_strategy=MaxRetriesStopStrategy(max_retries))


    with GarminClient(username, password) as client:
        # get all activity ids and timestamps from Garmin account
        log.info("scanning activities for %s ...", username)
        activities = set(retryer.call(client.list_activities))
        log.info("account has a total of %d activities", len(activities))

        missing_activities = garminexport.backup.need_backup(
            activities, backup_dir, format)
        backed_up = activities - missing_activities
        log.info("%s contains %d backed up activities",
            backup_dir, len(backed_up))

        log.info("activities that aren't backed up: %d",
                    len(missing_activities))

        for index, activity in enumerate(missing_activities):
            id, start = activity
            log.info("backing up activity %d from %s (%d out of %d) ..." % (id, start, index+1, len(missing_activities)))
            try:
                garminexport.backup.download(
                    client, activity, retryer, backup_dir,
                    format)
            except Exception as e:
                log.error(u"failed with exception: %s", e)
                if not ignore_errors:
                    raise

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Performs incremental backups of activities for a "
            "given Garmin Connect account. Only activities that "
            "aren't already stored in the backup directory will "
            "be downloaded."))
    # positional args
    parser.add_argument(
        "username", metavar="<username>", type=str, help="Account user name.")
    # optional args
    parser.add_argument(
        "--password", type=str, help="Account password.")
    parser.add_argument(
        "--backup-dir", metavar="DIR", type=str,
        help=("Destination directory for downloaded activities. Default: "
              "./activities/"), default=os.path.join(".", "activities"))
    parser.add_argument(
        "--log-level", metavar="LEVEL", type=str,
        help=("Desired log output level (DEBUG, INFO, WARNING, ERROR). "
              "Default: INFO."), default="INFO")
    parser.add_argument(
        "-f", "--format", choices=export_formats,
        default=None, action='append',
        help=("Desired output formats ("+', '.join(export_formats)+"). "
              "Default: ALL."))
    parser.add_argument(
        "-E", "--ignore-errors", action='store_true',
        help="Ignore errors and keep going. Default: FALSE")
    parser.add_argument(
        "--max-retries", metavar="NUM", default=DEFAULT_MAX_RETRIES,
        type=int, help="The maximum number of retries to make on failed attempts to fetch an activity. Exponential backoff will be used, meaning that the delay between successive attempts will double with every retry, starting at one second. DEFAULT: %d" % DEFAULT_MAX_RETRIES)

    args = parser.parse_args()
    if not args.log_level in LOG_LEVELS:
        raise ValueError("Illegal log-level: {}".format(args.log_level))

    # if no --format was specified, all formats are to be backed up
    args.format = args.format if args.format else export_formats
    log.info("backing up formats: %s", ", ".join(args.format))

    logging.root.setLevel(LOG_LEVELS[args.log_level])

    try:
        if not os.path.isdir(args.backup_dir):
            os.makedirs(args.backup_dir)

        if not args.password:
            args.password = getpass.getpass("Enter password: ")

        # set up a retryer that will handle retries of failed activity downloads
        get_garmin_connect_data(args.username,args.password,args.backup_dir,args.log_level,args.format,args.ignore_errors,args.max_retries)
        
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        log.error(u"failed with exception: %s", str(e))

if __name__ == "__main__":
    main()
    
