"""This script performs backups of activities for a Garmin Connect account.  The
activities are stored in a local directory on the user's computer.  The backups
are incremental, meaning that only activities that aren't already stored in the
backup directory will be downloaded.

"""
import argparse
import logging
import os

from garminexport.backup import supported_export_formats
from garminexport.incremental_backup import incremental_backup
from garminexport.logging_config import LOG_LEVELS

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 7
"""The default maximum number of retries to make when fetching a single activity."""

DEFAULT_USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36'
"""The default `User-Agent` to use for HTTP requests when none is supplied by
the user.
"""

def parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    :return: Namespace object holding parsed arguments as attributes.
    This object may be directly used by garminexport/garminbackup.py.
    """
    parser = argparse.ArgumentParser(
        prog="garminbackup",
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
        help="Destination directory for downloaded activities. Default: ./activities/",
        default=os.path.join(".", "activities"))
    parser.add_argument(
        "--log-level", metavar="LEVEL", type=str,
        help="Desired log output level (DEBUG, INFO, WARNING, ERROR). Default: INFO.",
        default="INFO")
    parser.add_argument(
        "-f", "--format", choices=supported_export_formats,
        default=None, action='append',
        help="Desired output formats ({}). Default: ALL.".format(', '.join(supported_export_formats)))
    parser.add_argument(
        "-E", "--ignore-errors", action='store_true',
        help="Ignore errors and keep going. Default: FALSE")
    parser.add_argument(
        "--max-retries", metavar="NUM", default=DEFAULT_MAX_RETRIES,
        type=int,
        help=("The maximum number of retries to make on failed attempts to fetch an activity. "
              "Exponential backoff will be used, meaning that the delay between successive attempts "
              "will double with every retry, starting at one second. DEFAULT: {}").format(DEFAULT_MAX_RETRIES))
    parser.add_argument(
        "--user-agent", type=str, default=DEFAULT_USER_AGENT,
        help="A value to use for the `User-Agent` request header. Use an authentic browser agent string to prevent being blocked by Garmin. A tool such as `user_agent` (`ua`) can be used to generate such values.")
    parser.add_argument(
        "--domain", metavar="com", type=str,
        help="Top level domain of your Garmin Connect website. Default: com.",
        default="com")

    return parser.parse_args()


def main():
    args = parse_args()
    logging.root.setLevel(LOG_LEVELS[args.log_level])

    try:
        incremental_backup(username=args.username,
                           password=args.password,
                           user_agent_fn=lambda:DEFAULT_USER_AGENT,
                           backup_dir=args.backup_dir,
                           export_formats=args.format,
                           ignore_errors=args.ignore_errors,
                           max_retries=args.max_retries,
                           domain=args.domain)

    except Exception as e:
        log.error("failed with exception: {}".format(e))
