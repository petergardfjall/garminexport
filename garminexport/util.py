#! /usr/bin/env python
"""A module with utility functions."""

import codecs
import json
from datetime import datetime
import dateutil.parser
import os

export_formats=["json_summary", "json_details", "gpx", "tcx", "fit"]

def export_activity(client, activity_id, destination,
                    formats=None):
    """Exports a Garmin Connect activity to a given set of formats
    and saves the result file(es) to a given destination directory.

    :param client: A :class:`garminexport.garminclient.GarminClient`
      instance that is assumed to be connected.
    :type client: :class:`garminexport.garminclient.GarminClient`
    :param activity_id: Activity identifier.
    :type activity_id: int
    :param destination: Destination directory (assumed to exist already).
    :type destination: str

    :keyword formats: Which format(s) to export to. Could be any
      of: 'json_summary', 'json_details', 'gpx', 'tcx', 'fit'.
      If set to :obj:`None`  all formats will be exported.
    :type formats: list of str
    """
    if formats is None:
        formats = export_formats
    activity_summary = client.get_activity_summary(activity_id)
    
    # prefix saved activity files with timestamp and activity id
    start = activity_summary["activity"]["activitySummary"]["BeginTimestamp"]["value"]
    timestamp = dateutil.parser.parse(start)
    filename_prefix = "{}_{}".format(timestamp.isoformat(), activity_id)
    path_prefix = os.path.join(destination, filename_prefix)
    
    if 'json_summary' in formats:
        summary_file = path_prefix + "_summary.json"
        with codecs.open(summary_file, encoding="utf-8", mode="w") as f:
            f.write(json.dumps(
                activity_summary, ensure_ascii=False, indent=4))
            
    if 'json_details' in formats:
        activity_details = client.get_activity_details(activity_id)
        details_file = path_prefix + "_details.json"
        with codecs.open(details_file, encoding="utf-8", mode="w") as f:
            f.write(json.dumps(
                activity_details, ensure_ascii=False, indent=4))
            
    if 'gpx' in formats:
        activity_gpx = client.get_activity_gpx(activity_id)
        gpx_file = path_prefix + ".gpx"
        with codecs.open(gpx_file, encoding="utf-8", mode="w") as f:
            f.write(activity_gpx)
            
    if 'tcx' in formats:
        activity_tcx = client.get_activity_tcx(activity_id)
        tcx_file = path_prefix + ".tcx"
        with codecs.open(tcx_file, encoding="utf-8", mode="w") as f:
            f.write(activity_tcx)
            
    if 'fit' in formats:
        activity_fit = client.get_activity_fit(activity_id)
        fit_file = path_prefix + ".fit"
        if activity_fit:
            with open(fit_file, mode="wb") as f:
                f.write(activity_fit)
    
