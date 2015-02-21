#! /usr/bin/env python
"""A program that downloads all activities for a given Garmin Connect account
and stores them locally on the user's computer.
"""
import argparse
import getpass
from garminexport.garminclient import GarminClient
import garminexport.util
import logging
import os
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
        description="Downloads all activities for a given Garmin Connect account.")
    # positional args
    parser.add_argument(
        "username", metavar="<username>", type=str, help="Account user name.")
    # optional args
    parser.add_argument(
        "--password", type=str, help="Account password.")
    parser.add_argument(
        "--destination", metavar="DIR", type=str,
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
        if not os.path.isdir(args.destination):
            os.makedirs(args.destination)

        if not args.password:
            args.password = getpass.getpass("Enter password: ")
        
        with GarminClient(args.username, args.password) as client:
            log.info("fetching activities for {} ...".format(args.username))
            all_activities = client.list_activities()
            for index, (id, start, stat) in enumerate(activity_ids):
                log.info("processing activity {} from {} ({} out of {}) ...".format(
                    id, start, index+1, len(activity_ids)))
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
