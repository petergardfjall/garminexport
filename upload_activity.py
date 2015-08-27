#! /usr/bin/env python
"""A program that uploads an activity file to a Garmin
Connect account.
"""
import argparse
import getpass
from garminexport.garminclient import GarminClient
import logging
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
        description=("Uploads an activity file to a Garmin Connect account."))
    # positional args
    parser.add_argument(
        "username", metavar="<username>", type=str, help="Account user name.")
    parser.add_argument(
        "activity", metavar="<file>", type=argparse.FileType("rb"),
        help="Activity file (.gpx, .tcx, or .fit).")

    # optional args
    parser.add_argument(
        "--password", type=str, help="Account password.")
    parser.add_argument(
        '-N', '--name', help="Activity name on Garmin Connect.")
    parser.add_argument(
        '-D', '--description', help="Activity description on Garmin Connect.")
    parser.add_argument(
        '-P', '--private', action='store_true', help="Make activity private on Garmin Connect.")
    parser.add_argument(
        "--log-level", metavar="LEVEL", type=str,
        help=("Desired log output level (DEBUG, INFO, WARNING, ERROR). "
              "Default: INFO."), default="INFO")

    args = parser.parse_args()
    if not args.log_level in LOG_LEVELS:
        raise ValueError("Illegal log-level argument: {}".format(
            args.log_level))
    logging.root.setLevel(LOG_LEVELS[args.log_level])

    try:
        if not args.password:
            args.password = getpass.getpass("Enter password: ")
        with GarminClient(args.username, args.password) as client:
            log.info("uploading activity file {} ...".format(args.activity.name))
            id = client.upload_activity(args.activity, name=args.name, description=args.description, private=args.private)
            log.info("upload successful: https://connect.garmin.com/activity/{}".format(id))
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        log.error(u"failed with exception: %s", e)
        raise

