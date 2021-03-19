import logging

from garminexport.garminexport.garminclient import GarminClient

logging.basicConfig(level=logging.DEBUG, format="%(asctime)-15s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

with GarminClient('my@email.com', 'password') as client:
    activities = client.get_activities()
    log.info("num ids: %d", len(activities))

    for activity in activities:
        if activity['activityType']['typeKey'] == 'other':
            activity_id = activity['activityId']
            log.info(f"Got an untyped activity : {activity_id}")
            client.update_activity(activity_id, 'activityTypeDTO', {"typeKey": "indoor_cardio"})
            client.update_activity(activity_id, 'eventTypeDTO', {"typeKey": "training"})
