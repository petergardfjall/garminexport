#! /usr/bin/env python

import argparse
import getpass
import json
import logging

from garminexport.garminclient import GarminClient

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Export all Garmin Connect activities")
    # positional args
    parser.add_argument(
        "username", metavar="<username>", type=str, help="Account user name.")
    # optional args
    parser.add_argument(
        "--password", type=str, help="Account password.")

    args = parser.parse_args()
    print(args)

    if not args.password:
        args.password = getpass.getpass("Enter password: ")

    try:
        with GarminClient(args.username, args.password) as client:
            activity_ids = client.list_activities()
            log.info("num ids: %d", len(activity_ids))
            latest_activity, latest_activity_start = activity_ids[0]
            activity = client.get_activity_summary(latest_activity)
            log.info("activity id: %s", activity["activityId"])
            log.info("activity name: '%s'", activity["activityName"])
            log.info(json.dumps(client.get_activity_details(latest_activity), indent=4))
            log.info(client.get_activity_gpx(latest_activity))
    except Exception as e:
        log.error("failed with exception: %s", e)
    finally:
        log.info("done")
