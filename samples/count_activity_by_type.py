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

    activities_by_type = {}
    for activity in activities:
        activity_type = activity['activityType']['typeKey']
        if not activities_by_type.get(activity_type):
            activities_by_type[activity_type] = []
        activities_by_type[activity_type].append(activity)

    log.info(f"Found the following activities : {activities_by_type.keys()}")

    for activity_type in activities_by_type.keys():
        log.info(f"Found {len(activities_by_type[activity_type])} {activity_type} activities.")
