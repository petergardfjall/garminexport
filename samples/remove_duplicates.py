import json
import logging
from datetime import date

import dateutil.parser

logging.basicConfig(level=logging.DEBUG, format="%(asctime)-15s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# with GarminClient('my@email.com', 'password') as client:
#    activities = client.get_activities()
with open('../../data/activities.json') as f:
    activities = json.loads(f.read())
    log.info("Loading %d activities", len(activities))

    duplicates = []
    i: int = 0
    while i < len(activities):
        activity_i = activities[i]
        activity_i_date: date = dateutil.parser.parse(activity_i["startTimeGMT"]).date()
        activity_i_type = activity_i['activityType']['typeKey']
        j: int = len(activities) - 1
        while j > i:
            activity_j = activities[j]
            activity_j_date: date = dateutil.parser.parse(activity_j["startTimeGMT"]).date()
            activity_j_type = activity_j['activityType']['typeKey']
            # Evaluate by date (ignoring hours)
            if activity_i_date == activity_j_date and (
                    activity_i_type == 'lap_swimming' or activity_j_type == 'lap_swimming'):
                duplicates.append([activity_i, activity_j])
            j -= 1
        i += 1

    log.info(f"Found %d swim duplicates", len(duplicates))
    for activity in duplicates:
        log.info("Duplicate at {}".format(dateutil.parser.parse(activity[0]["startTimeGMT"]).date()))
