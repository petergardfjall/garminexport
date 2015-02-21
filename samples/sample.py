#! /usr/bin/env python

import argparse
import getpass
from garminexport.garminclient import GarminClient
import json
import logging
import sys

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
            log.info("activities:")
            activity_ids = client.list_activities()
            log.info("num ids: {}".format(len(activity_ids)))
            log.info(activity_ids)

            latest_activity, latest_activity_start, latest_activity_stationary = activity_ids[0]
            activity = client.get_activity_summary(latest_activity)
            log.info(u"activity id: %s", activity["activity"]["activityId"])
            log.info(u"activity name: '%s'", activity["activity"]["activityName"])
            log.info(u"activity description: '%s'", activity["activity"]["activityDescription"])
            log.info(json.dumps(client.get_activity_details(latest_activity), indent=4))
            log.info(client.get_activity_gpx(latest_activity))
    except Exception as e:
        log.error(u"failed with exception: %s", e)
    finally:            
        log.info("done")
