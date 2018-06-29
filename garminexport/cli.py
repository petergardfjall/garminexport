import argparse
import os

from garminexport.backup import supported_export_formats

DEFAULT_MAX_RETRIES = 7
"""The default maximum number of retries to make when fetching a single activity."""


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    :return: Namespace object holding parsed arguments as attributes.
    This object may be directly used by garminexport/garminbackup.py.
    """
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

    return parser.parse_args()
