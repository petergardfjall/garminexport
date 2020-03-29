#! /usr/bin/env python
"""This python script calls garminexport.garminbackup module with CLI parsed arguments
and performs (incremental) backups of activities for a given Garmin Connect account.
The activities are stored in a local directory on the user's computer.
The backups are incremental, meaning that only activities that aren't already
stored in the backup directory will be downloaded.
"""
import logging

from garminexport.cli import parse_args
from garminexport.incremental_backup import incremental_backup
from garminexport.logging_config import LOG_LEVELS

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

if __name__ == "__main__":
    args = parse_args()
    logging.root.setLevel(LOG_LEVELS[args.log_level])

    try:
        incremental_backup(username=args.username,
                           password=args.password,
                           backup_dir=args.backup_dir,
                           format=args.format,
                           ignore_errors=args.ignore_errors,
                           max_retries=args.max_retries)

    except Exception as e:
        log.error("failed with exception: {}".format(e))
