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
    parser.add_argument(
        "--domain", metavar="com", type=str,
        help="Top level domain of your Garmin Connect website. Default: com.",
        default="INFO")

    args = parser.parse_args()
    print(args)

    if not args.password:
        args.password = getpass.getpass("Enter password: ")

    try:
        with GarminClient(args.username, args.password, domain=args.domain) as client:
            log.info("activities:")
            activity_ids = client.list_activities()
            log.info("num ids: %d", len(activity_ids))
            log.info(activity_ids)

            latest_activity, latest_activity_start = activity_ids[0]
            activity = client.get_activity_summary(latest_activity)
            log.info("activity id: %s", activity["activity"]["activityId"])
            log.info("activity name: '%s'", activity["activity"]["activityName"])
            log.info("activity description: '%s'", activity["activity"]["activityDescription"])
            log.info(json.dumps(client.get_activity_details(latest_activity), indent=4))
            log.info(client.get_activity_gpx(latest_activity))
    except Exception as e:
        log.error("failed with exception: %s", e)
    finally:
        log.info("done")
