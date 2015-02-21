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
import garminexport.util
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

def get_backed_up(activities, backup_dir, formats):
    """Return all activity (id, ts) pairs that have been backed up in the
    given backup directory.

    :rtype: list of int
    """
    # backed up activities follow this pattern: <ISO8601>_<id>_<suffix>
    format_suffix = dict(json_summary="_summary.json", json_details="_details.json", gpx=".gpx", tcx=".tcx", fit=".fit")
    
    backed_up = set()
    dir_entries = os.listdir(backup_dir)
    for id, start in activities:
        if all( "{}_{}{}".format(start.isoformat(), id, format_suffix[f]) in dir_entries for f in formats):
            backed_up.add((id, start))
    return backed_up


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
        "-f", "--format", choices=garminexport.util.export_formats,
        default=None, action='append',
        help=("Desired output formats ("+', '.join(garminexport.util.export_formats)+"). "
              "Default: ALL."))
    parser.add_argument(
        "-E", "--ignore-errors", action='store_true',
        help="Ignore errors and keep going. Default: FALSE")
    
    args = parser.parse_args()
    if not args.log_level in LOG_LEVELS:
        raise ValueError("Illegal log-level argument: {}".format(args.log_level))
    logging.root.setLevel(LOG_LEVELS[args.log_level])
        
    try:
        if not os.path.isdir(args.backup_dir):
            os.makedirs(args.backup_dir)
            
        if not args.password:
            args.password = getpass.getpass("Enter password: ")
        
        with GarminClient(args.username, args.password) as client:
            # get all activity ids and timestamps from Garmin account
            log.info("retrieving activities for {} ...".format(args.username))
            all_activities = set(client.list_activities())
            log.info("account has a total of {} activities.".format(
                len(all_activities)))
            
            # get already backed up activities (stored in backup-dir)
            backed_up_activities = get_backed_up(all_activities, args.backup_dir, args.format)
            log.info("{} contains {} backed up activities.".format(
                args.backup_dir, len(backed_up_activities)))

            missing_activities = all_activities - backed_up_activities
            log.info("activities that haven't been backed up: {}".format(
                len(missing_activities)))
            
            for index, (id, start) in enumerate(missing_activities):
                log.info("backing up activity {} from {} ({} out of {}) ...".format(
                    id, start, index+1, len(missing_activities)))
                try:
                    garminexport.util.export_activity(
                        client, id, args.backup_dir, args.format)
                except Exception as e:
                    log.error(u"failed with exception: %s", e)
                    if not args.ignore_errors:
                        raise
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        log.error(u"failed with exception: %s", e)
        raise
