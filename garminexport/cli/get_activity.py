#! /usr/bin/env python
"""A program that downloads one particular activity from a given Garmin
Connect account and stores it locally on the user's computer.
"""
import argparse
import getpass
import logging
import os
from datetime import timedelta

import dateutil.parser

import garminexport.backup
from garminexport.garminclient import GarminClient
from garminexport.logging_config import LOG_LEVELS
from garminexport.retryer import Retryer, ExponentialBackoffDelayStrategy, MaxRetriesStopStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Downloads one particular activity for a given Garmin Connect account.")

    # positional args
    parser.add_argument(
        "username", metavar="<username>", type=str, help="Account user name.")
    parser.add_argument(
        "activity", metavar="<activity>", type=int, help="Activity ID.")
    parser.add_argument(
        "format", metavar="<format>", type=str,
        help="Export format (one of: {}).".format(garminexport.backup.supported_export_formats))

    # optional args
    parser.add_argument(
        "--password", type=str, help="Account password.")
    parser.add_argument(
        "--destination", metavar="DIR", type=str,
        help="Destination directory for downloaded activity. Default: ./activities/",
        default=os.path.join(".", "activities"))
    parser.add_argument(
        "--log-level", metavar="LEVEL", type=str,
        help="Desired log output level (DEBUG, INFO, WARNING, ERROR). Default: INFO.",
        default="INFO")
    parser.add_argument(
        "--token",
        default=None,
        type=str,
        help=("Authentication header token. Use with 'jwt_fgp' instead of username and password, for example "
              "if login fails due to ReCaptcha."))
    parser.add_argument(
        "--jwt_fgp",
        default=None,
        type=str,
        help=("Authentication JWT_FGP Cookie. Use with 'token' instead of username and password, for example "
              "if login fails due to ReCaptcha."))

    args = parser.parse_args()

    if args.log_level not in LOG_LEVELS:
        raise ValueError("Illegal log-level argument: {}".format(args.log_level))

    if args.format not in garminexport.backup.supported_export_formats:
        raise ValueError(
            "Unrecognized export format: '{}'. Must be one of {}".format(
                args.format, garminexport.backup.supported_export_formats))

    logging.root.setLevel(LOG_LEVELS[args.log_level])

    try:
        if not os.path.isdir(args.destination):
            os.makedirs(args.destination)

        prompt_password = not args.password and (not args.token or not args.jwt_fgp)
        if prompt_password:
            args.password = getpass.getpass("Enter password: ")

        with GarminClient(args.username, args.password, args.token, args.jwt_fgp) as client:
            log.info("fetching activity %s ...", args.activity)
            summary = client.get_activity_summary(args.activity)
            # set up a retryer that will handle retries of failed activity downloads
            retryer = Retryer(
                delay_strategy=ExponentialBackoffDelayStrategy(initial_delay=timedelta(seconds=1)),
                stop_strategy=MaxRetriesStopStrategy(5))

            start_time = dateutil.parser.parse(summary["summaryDTO"]["startTimeGMT"])
            garminexport.backup.download(
                client, (args.activity, start_time), retryer, args.destination, export_formats=[args.format])
    except Exception as e:
        log.error("failed with exception: %s", e)
        raise
