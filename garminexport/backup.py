"""Module with methods useful when backing up activities.
"""
import codecs
import json
from datetime import datetime
import dateutil.parser
import logging
import os

log = logging.getLogger(__name__)

export_formats=["json_summary", "json_details", "gpx", "tcx", "fit"]
"""The range of supported export formats for activities."""

format_suffix = {
    "json_summary": "_summary.json",
    "json_details": "_details.json",
    "gpx": ".gpx",
    "tcx": ".tcx",
    "fit": ".fit"
}
"""A table that maps export formats to their file format extensions."""


not_found_file = ".not_found"
"""A file that lists all tried but failed export attempts. The lines in
the file are the would-have-been file names, had the exports been successful.
An entry in the ``.not_found`` file is a strong indication of an
activity-format that simply doesn't exist and therefore should not be retried
on the next backup run. One such scenario is for manually created activities,
which cannot be exported to ``.fit`` format."""


def export_filename(activity, export_format):
    """Returns a destination file name to use for a given activity that is
    to be exported to a given format. Exported files follow this pattern:
      ``<timestamp>_<activity_id>_<suffix>``.
    For example: ``2015-02-17T05:45:00+00:00_123456789.tcx``

    :param activity: An activity tuple `(id, starttime)`
    :type activity: tuple of `(int, datetime)`
    :param export_format: The export format (see :attr:`export_formats`)
    :type export_format: str

    :return: The file name to use for the exported activity.
    :rtype: str
    """
    fn = "{time}_{id}{suffix}".format(
        id=activity[0],
        time=activity[1].isoformat(),
        suffix=format_suffix[export_format])
    return fn.replace(':','_') if os.name=='nt' else fn


def need_backup(activities, backup_dir, export_formats=None):
    """From a given set of activities, return all activities that haven't been
    backed up in a given set of export formats.

    Activities are considered already backed up if they, for each desired
    export format, have an activity file under the ``backup_dir`` *or*
    if the activity file is listed in the ``.not_found`` file in the backup
    directory.

    :param activities: A list of activity tuples `(id, starttime)`
    :type activities: list of tuples of `(int, datetime)`
    :param backup_dir: Destination directory for exported activities.
    :type backup_dir: str
    :return: All activities that need to be backed up.
    :rtype: set of tuples of `(int, datetime)`
    """
    need_backup = set()
    backed_up = os.listdir(backup_dir) + _not_found_activities(backup_dir)

    # get all activities missing at least one export format
    for activity in activities:
        activity_files = [export_filename(activity, f) for f in export_formats]
        if any(f not in backed_up for f in activity_files):
            need_backup.add(activity)
    return need_backup


def _not_found_activities(backup_dir):
    # consider all entries in <backup_dir>/.not_found as backed up
    # (or rather, as tried but failed back ups)
    failed_activities = []
    _not_found = os.path.join(backup_dir, not_found_file)
    if os.path.isfile(_not_found):
        with open(_not_found, mode="r") as f:
            failed_activities = [line.strip() for line in f.readlines()]
    log.debug("%d tried but failed activities in %s",
              len(failed_activities), _not_found)
    return failed_activities



def download(client, activity, retryer, backup_dir, export_formats=None):
    """Exports a Garmin Connect activity to a given set of formats
    and saves the resulting file(s) to a given backup directory.
    In case a given format cannot be exported for the activity, the
    file name will be appended to the :attr:`not_found_file` in the
    backup directory (to prevent it from being retried on subsequent
    backup runs).

    :param client: A :class:`garminexport.garminclient.GarminClient`
      instance that is assumed to be connected.
    :type client: :class:`garminexport.garminclient.GarminClient`
    :param activity: An activity tuple `(id, starttime)`
    :type activity: tuple of `(int, datetime)`
    :param retryer: A :class:`garminexport.retryer.Retryer` instance that
      will handle failed download attempts.
    :type retryer: :class:`garminexport.retryer.Retryer`
    :param backup_dir: Backup directory path (assumed to exist already).
    :type backup_dir: str
    :keyword export_formats: Which format(s) to export to. Could be any
      of: 'json_summary', 'json_details', 'gpx', 'tcx', 'fit'.
    :type export_formats: list of str
    """
    id = activity[0]

    if 'json_summary' in export_formats:
        log.debug("getting json summary for %s", id)

        activity_summary = retryer.call(client.get_activity_summary, id)
        dest = os.path.join(
            backup_dir, export_filename(activity, 'json_summary'))
        with codecs.open(dest, encoding="utf-8", mode="w") as f:
            f.write(json.dumps(
                activity_summary, ensure_ascii=False, indent=4))

     if 'json_details' in export_formats:
         log.debug("getting json details for %s", id)
         """Do not skip gqx, tcx and fit files only because
            json_details does not exist.
         """
         try:
             activity_details = retryer.call(client.get_activity_details, id)
             dest = os.path.join(
                 backup_dir, export_filename(activity, 'json_details'))
             with codecs.open(dest, encoding="utf-8", mode="w") as f:
                 f.write(json.dumps(
                     activity_details, ensure_ascii=False, indent=4))
         except Exception as e:
             log.error(u"failed with exception: %s", e)


    not_found_path = os.path.join(backup_dir, not_found_file)
    with open(not_found_path, mode="a") as not_found:
        if 'gpx' in export_formats:
            log.debug("getting gpx for %s", id)
            activity_gpx = retryer.call(client.get_activity_gpx, id)
            dest = os.path.join(
                backup_dir, export_filename(activity, 'gpx'))
            if activity_gpx is None:
                not_found.write(os.path.basename(dest) + "\n")
            else:
                with codecs.open(dest, encoding="utf-8", mode="w") as f:
                    f.write(activity_gpx)

        if 'tcx' in export_formats:
            log.debug("getting tcx for %s", id)
            activity_tcx = retryer.call(client.get_activity_tcx, id)
            dest = os.path.join(
                backup_dir, export_filename(activity, 'tcx'))
            if activity_tcx is None:
                not_found.write(os.path.basename(dest) + "\n")
            else:
                with codecs.open(dest, encoding="utf-8", mode="w") as f:
                    f.write(activity_tcx)

        if 'fit' in export_formats:
            log.debug("getting fit for %s", id)
            activity_fit = retryer.call(client.get_activity_fit, id)
            dest = os.path.join(
                backup_dir, export_filename(activity, 'fit'))
            if activity_fit is None:
                not_found.write(os.path.basename(dest) + "\n")
            else:
                with open(dest, mode="wb") as f:
                    f.write(activity_fit)
