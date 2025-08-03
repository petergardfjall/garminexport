#! /usr/bin/env python
import logging
import os
from datetime import timedelta
from typing import Callable, List

import garminexport.backup
from garminexport.backup import supported_export_formats
from garminexport.garminclient import GarminClient
from garminexport.retryer import Retryer, ExponentialBackoffDelayStrategy, MaxRetriesStopStrategy

log = logging.getLogger(__name__)


def incremental_backup(bearer_token: str = None,
                       jwt_fgp_cookie: str = None,

                       backup_dir: str = os.path.join(".", "activities"),
                       export_formats: List[str] = None,
                       ignore_errors: bool = False,
                       max_retries: int = 7):
    """Performs (incremental) backups of activities for a given Garmin Connect account.

    :param bearer_token: This is the OAuth bearer token to use for the
    Authorization header in client requests. It needs to be extracted using web
    browser developer tools from an active Garmin Connect session (with a
    successful login).

    :param jwt_fgp_cookie: This is the JWT_FGP cookie to use in client
    requests. It needs to be extracted using web browser developer tools from
    an active Garmin Connect session (with a successful login).

    :param backup_dir: Destination directory for downloaded
    activities. Default: ./activities/".

    :param export_formats: List of desired output formats (json_summary,
    json_details, gpx, tcx, fit).  Default: `None` which means all supported
    formats will be backed up.

    :param ignore_errors: Ignore errors and keep going. Default: False.

    :param max_retries: The maximum number of retries to make on failed
    attempts to fetch an activity. Exponential backoff will be used, meaning
    that the delay between successive attempts will double with every retry,
    starting at one second. Default: 7.

    The activities are stored in a local directory on the user's computer.  The
    backups are incremental, meaning that only activities that aren't already
    stored in the backup directory will be downloaded.

    """
    # if no --format was specified, all formats are to be backed up
    export_formats = export_formats if export_formats else supported_export_formats
    log.info("backing up formats: %s", ", ".join(export_formats))

    if not os.path.isdir(backup_dir):
        os.makedirs(backup_dir)

    if not bearer_token:
        bearer_token = input("Enter Authorization header bearer token (extract with web browser developer tools): ")
    if not jwt_fgp_cookie:
        jwt_fgp_cookie = input("Enter JWT_FGP cookie value (extract with web browser developer tools): ")

    # set up a retryer that will handle retries of failed activity downloads
    retryer = Retryer(
        delay_strategy=ExponentialBackoffDelayStrategy(initial_delay=timedelta(seconds=1)),
        stop_strategy=MaxRetriesStopStrategy(max_retries))

    with GarminClient(bearer_token, jwt_fgp_cookie) as client:
        # get all activity ids and timestamps from Garmin account
        log.info("scanning activities ...")
        activities = set(retryer.call(client.list_activities))
        log.info("account has a total of %d activities", len(activities))

        missing_activities = garminexport.backup.need_backup(activities, backup_dir, export_formats)
        backed_up = activities - missing_activities
        log.info("%s contains %d backed up activities", backup_dir, len(backed_up))

        log.info("activities that aren't backed up: %d", len(missing_activities))

        for index, activity in enumerate(missing_activities):
            id, start = activity
            log.info("backing up activity %s from %s (%d out of %d) ...",
                     id, start, index + 1, len(missing_activities))
            try:
                garminexport.backup.download(client, activity, retryer, backup_dir, export_formats)
            except Exception as e:
                log.error("failed with exception: %s", e)
                if not ignore_errors:
                    raise
