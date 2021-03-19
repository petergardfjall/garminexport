import json
import logging

from garminexport.garminexport.garminclient import GarminClient

logging.basicConfig(level=logging.DEBUG, format="%(asctime)-15s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

with GarminClient('my@email.com', 'password') as client:
    activities = client.get_activities()
    log.info("Stored %d activities", len(activities))
    with open('../../data/activities.json', "w") as f:
        f.write(json.dumps(activities, ensure_ascii=False, indent=4))
