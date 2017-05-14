#! /usr/bin/env python
"""Performs (incremental) backups of activities for a given Garmin Connect
account.
The activities are stored in a local directory on the user's computer.
The backups are incremental, meaning that only activities that aren't already
stored in the backup directory will be downloaded.
"""
import argparse
import getpass
from garminexport.garminclient import GarminClient
import garminexport.backup
from garminexport.backup import export_formats
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



if __name__ == "__main__":
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

        with GarminClient(args.username, args.password) as client:
            # get all activity ids and timestamps from Garmin account
            log.info("scanning activities for %s ...", args.username)
            activities = set(client.list_activities())
            log.info("account has a total of %d activities", len(activities))

            missing_activities = garminexport.backup.need_backup(
                activities, args.backup_dir, args.format)
            backed_up = activities - missing_activities
            log.info("%s contains %d backed up activities",
                args.backup_dir, len(backed_up))

            log.info("activities that aren't backed up: %d",
                     len(missing_activities))

            for index, activity in enumerate(missing_activities):
                id, start = activity
                log.info("backing up activity %d from %s (%d out of %d) ..." %
                         (id, start, index+1, len(missing_activities)))
                try:
                    garminexport.backup.download(
                        client, activity, args.backup_dir, args.format)
                except Exception as e:
                    log.error(u"failed with exception: %s", e)
                    if not args.ignore_errors:
                        raise
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        log.error(u"failed with exception: %s", str(e))
