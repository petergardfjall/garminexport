import json
import logging

logging.basicConfig(level=logging.DEBUG, format="%(asctime)-15s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

with open('../../data/activities.json') as f:
    activities = json.loads(f.read())
    log.info("Loading %d activities", len(activities))
