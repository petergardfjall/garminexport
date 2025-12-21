#! /usr/bin/env python
"""A program that uploads an activity file to a Garmin Connect account.
"""
import argparse
import getpass
import logging

from garminexport.garminclient import GarminClient
from garminexport.logging_config import LOG_LEVELS
from garminexport.cli.backup import DEFAULT_AUTH_TOKEN_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Uploads an activity file to a Garmin Connect account.")

    # positional args
    parser.add_argument(
        "username", metavar="<username>", type=str, help="Account user name.")
    parser.add_argument(
        "activity", nargs='+', metavar="<file>", type=argparse.FileType("rb"),
        help="Activity file (.gpx, .tcx, or .fit).")

    # optional args
    parser.add_argument(
        "--password", type=str, help="Account password.")
    parser.add_argument(
        "--auth-token-dir", metavar="DIR", type=str,
        help=f"Folder where auth tokens saved. Default: {DEFAULT_AUTH_TOKEN_DIR}",
        default=DEFAULT_AUTH_TOKEN_DIR)
    parser.add_argument(
        '-N', '--name', help="Activity name on Garmin Connect.")
    parser.add_argument(
        '-D', '--description', help="Activity description on Garmin Connect.")
    parser.add_argument(
        '-P', '--private', action='store_true', help="Make activity private on Garmin Connect.")
    parser.add_argument(
        '-T', '--type', help="Override activity type (running, cycling, walking, hiking, strength_training, etc.)")
    parser.add_argument(
        "--log-level", metavar="LEVEL", type=str,
        help="Desired log output level (DEBUG, INFO, WARNING, ERROR). Default: INFO.",
        default="INFO")

    args = parser.parse_args()

    if len(args.activity) > 1 and (args.description is not None or args.name is not None):
        parser.error("When uploading multiple activities, --name or --description cannot be used.")

    if args.log_level not in LOG_LEVELS:
        raise ValueError("Illegal log-level argument: {}".format(args.log_level))

    logging.root.setLevel(LOG_LEVELS[args.log_level])

    try:
        if not args.password:
            args.password = getpass.getpass("Enter password: ")

        client = GarminClient(args.username, args.password, args.auth_token_dir)
        client.connect()

        for activity in args.activity:
            log.info("uploading activity file %s ...", activity.name)
            try:
                id = client.upload_activity(activity, name=args.name, description=args.description,
                                            private=args.private, activity_type=args.type)
            except Exception as e:
                log.error("upload failed: {!r}".format(e))
            else:
                log.info("upload successful: https://connect.garmin.com/modern/activity/%s", id)

    except Exception as e:
        log.error("failed with exception: %s", e)
        raise
    finally:
        client.disconnect()
