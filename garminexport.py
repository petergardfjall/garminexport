#! /usr/bin/env python
"""A program that downloads all activities for a given Garmin Connect account
and stores them locally on the user's computer.
"""
import argparse
import codecs
from datetime import datetime
import getpass
from garminexport.garminclient import GarminClient
import io
import json
import logging
import os
import shutil
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
        help=("Destination directory for downloaded activities. "
              "Default: ./activities/<timestamp>/"),
        default=os.path.join(".", "activities", datetime.now().isoformat()))
    parser.add_argument(
        "--log-level", metavar="LEVEL", type=str,
        help=("Desired log output level (DEBUG, INFO, WARNING, ERROR). "
              "Default: INFO."), default="INFO")
    
    args = parser.parse_args()
    if not args.log_level in LOG_LEVELS:
        raise ValueError("Illegal log-level argument: {}".format(args.log_level))
    logging.root.setLevel(LOG_LEVELS[args.log_level])
        
    try:
        os.makedirs(args.destination)
        if not args.password:
            args.password = getpass.getpass("Enter password: ")
        
        with GarminClient(args.username, args.password) as client:
            log.info("fetching activities for {} ...".format(args.username))
            activity_ids = client.list_activity_ids()
            for index, id in enumerate(activity_ids):
                log.info("processing activity {} out of {} ...".format(
                    index+1, len(activity_ids)))
                activity_summary = client.get_activity_summary(id)
                activity_details = client.get_activity_details(id)
                activity_gpx = client.get_activity_gpx(id)
                activity_tcx = client.get_activity_tcx(id)
                activity_fit = client.get_activity_fit(id)
                
                # for each activitity save the summary, details and GPX file.
                creation_millis = activity_summary["activity"]["uploadDate"]["millis"]
                timestamp = datetime.fromtimestamp(int(creation_millis)/1000.0)
                filename_prefix = "{}_{}".format(
                    timestamp.strftime("%Y%m%d-%H%M%S"), id)
                path_prefix = os.path.join(args.destination, filename_prefix)
                
                summary_file = path_prefix + "_summary.json"
                details_file = path_prefix + "_details.json"
                gpx_file = path_prefix + ".gpx"
                tcx_file = path_prefix + ".tcx"
                fit_file = path_prefix + ".fit"
                with codecs.open(summary_file, encoding="utf-8", mode="w") as f:
                    f.write(json.dumps(
                        activity_summary, ensure_ascii=False, indent=4))
                with codecs.open(details_file, encoding="utf-8", mode="w") as f:
                    f.write(json.dumps(
                        activity_details, ensure_ascii=False, indent=4))
                with codecs.open(gpx_file, encoding="utf-8", mode="w") as f:
                    f.write(activity_gpx)
                with codecs.open(tcx_file, encoding="utf-8", mode="w") as f:
                    f.write(activity_tcx)
                with open(fit_file, mode="wb") as f:
                    f.write(activity_fit)
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        log.error(u"failed with exception: %s", e)
        raise

