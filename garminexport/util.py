#! /usr/bin/env python
"""A module with utility functions."""

import codecs
import json
from datetime import datetime
import os

def save_activity(client, activity_id, destination):
    """Downloads a certain Garmin Connect activity and saves it
    to a given destination directory.

    :param client: A :class:`garminexport.garminclient.GarminClient`
      instance that is assumed to be connected.
    :type client: :class:`garminexport.garminclient.GarminClient`
    :param activity_id: Activity identifier.
    :type activity_id: int
    :param destination: Destination directory (assumed to exist already).
    :type destination: str
    
    """
    activity_summary = client.get_activity_summary(activity_id)
    activity_details = client.get_activity_details(activity_id)
    activity_gpx = client.get_activity_gpx(activity_id)
    activity_tcx = client.get_activity_tcx(activity_id)
    activity_fit = client.get_activity_fit(activity_id)
                
    # save activitity summary, details and GPX, TCX and FIT file.
    creation_millis = activity_summary["activity"]["uploadDate"]["millis"]
    timestamp = datetime.fromtimestamp(int(creation_millis)/1000.0)
    filename_prefix = "{}_{}".format(
        timestamp.strftime("%Y%m%d-%H%M%S"), activity_id)
    path_prefix = os.path.join(destination, filename_prefix)
    
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
    if activity_fit:
        with open(fit_file, mode="wb") as f:
            f.write(activity_fit)
    
