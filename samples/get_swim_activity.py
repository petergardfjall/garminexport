import json
import logging

import dateutil.parser

from garminexport.garminexport.garminclient import GarminClient

logging.basicConfig(level=logging.DEBUG, format="%(asctime)-15s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

#with GarminClient('my@email.com', 'password') as client:
#    activities = client.get_activities()
with open('../../data/activities.json') as f:
    activities = json.loads(f.read())
    log.info("Loading %d activities", len(activities))

    swim = []
    for activity in activities:
        if activity["activityType"]["typeKey"] == 'lap_swimming':
            log.info("Found swim activity {}".format(dateutil.parser.parse(activity["startTimeGMT"]).date()))
            swim.append(activity)

    log.info(f"Found {len(swim)} swim activities")

    swim_candidates = []
    for activity in activities:
        if activity['movingDuration'] is not None and 2400 > activity['movingDuration'] > 1000 and activity[
            'distance'] is not None and 500 < activity['distance'] < 1500:
            swim_candidates.append(activity)
    log.info(f"Found {len(swim_candidates)} swim candidates")

    mistyped = []
    for activity in swim_candidates:
        if activity['activityType']['typeKey'] != 'lap_swimming':
            log.info("Found a mistyped swimming activity : {}".format(
                dateutil.parser.parse(activity["startTimeGMT"]).date()))
            mistyped.append(activity)

    for activity in mistyped:
        if activity['activityType']['typeKey'] == 'other':
            client.update_activity(activity['activityId'], 'activityTypeDTO', {"typeKey": "lap_swimming"})
