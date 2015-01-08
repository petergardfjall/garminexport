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

def get_backed_up_ids(backup_dir):
    """Return all activitiy ids that have been backed up in the
    given backup directory.

    :rtype: list of int
    """
    # backed up activities follow this pattern: <ISO8601>_<id>_summary.json
    activity_file_pattern = r'[\d:T\+\-]+_([0-9]+)_summary\.json'
    
    backed_up_ids = []
    dir_entries = os.listdir(backup_dir)
    for entry in dir_entries:
        activity_match = re.search(activity_file_pattern, entry)
        if activity_match:
            backed_up_id = int(activity_match.group(1))
            backed_up_ids.append(backed_up_id)
    return backed_up_ids           
    

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
            # already backed up activities (stored in backup-dir)
            backed_up_activities = set(get_backed_up_ids(args.backup_dir))
            log.info("{} contains {} backed up activities.".format(
                args.backup_dir, len(backed_up_activities)))

            # get all activity ids from Garmin account
            log.info("retrieving activities for {} ...".format(args.username))
            all_activities = set(client.list_activity_ids())
            log.info("account has a total of {} activities.".format(
                len(all_activities)))
            
            missing_activities = all_activities - backed_up_activities
            log.info("activities that haven't been backed up: {}".format(
                len(missing_activities)))
            
            for index, id in enumerate(missing_activities):
                log.info("backing up activity {} ({} out of {}) ...".format(
                    id, index+1, len(missing_activities)))
                garminexport.util.export_activity(
                    client, id, args.backup_dir)
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        log.error(u"failed with exception: %s", e)
        raise

