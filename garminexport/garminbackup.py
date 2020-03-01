#! /usr/bin/env python
import getpass
import logging
import os
import sys
from datetime import timedelta

import garminexport.backup
from garminexport.backup import export_formats
from garminexport.garminclient import GarminClient
from garminexport.retryer import Retryer, ExponentialBackoffDelayStrategy, MaxRetriesStopStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR
}
"""Command-line (string-based) log-level mapping to logging module levels."""


def garminbackup(args=None):
    """Performs (incremental) backups of activities for a given Garmin Connect account.

    :param args: an object with several attributes such as `username`, `password`, `backup_dir`, `format`, etc.

    The activities are stored in a local directory on the user's computer.
    The backups are incremental, meaning that only activities that aren't already
    stored in the backup directory will be downloaded.
    """
    if args.log_level not in LOG_LEVELS:
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

        # set up a retryer that will handle retries of failed activity
        # downloads
        retryer = Retryer(
            delay_strategy=ExponentialBackoffDelayStrategy(initial_delay=timedelta(seconds=1)),
            stop_strategy=MaxRetriesStopStrategy(args.max_retries))

        with GarminClient(args.username, args.password) as client:
            # get all activity ids and timestamps from Garmin account
            log.info("scanning activities for %s ...", args.username)
            activities = set(retryer.call(client.list_activities))
            log.info("account has a total of %d activities", len(activities))

            missing_activities = garminexport.backup.need_backup(activities, args.backup_dir, args.format)
            backed_up = activities - missing_activities
            log.info("%s contains %d backed up activities", args.backup_dir, len(backed_up))

            log.info("activities that aren't backed up: %d", len(missing_activities))

            for index, activity in enumerate(missing_activities):
                id, start = activity
                log.info("backing up activity %d from %s (%d out of %d) ..." % (
                    id, start, index + 1, len(missing_activities)))
                try:
                    garminexport.backup.download(client, activity, retryer, args.backup_dir, args.format)
                except Exception as e:
                    log.error(u"failed with exception: %s", e)
                    if not args.ignore_errors:
                        raise
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        log.error(u"failed with exception: %s", str(e))
