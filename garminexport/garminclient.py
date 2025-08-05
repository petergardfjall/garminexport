#! /usr/bin/env python
"""A module for authenticating against and communicating with selected
parts of the Garmin Connect REST API.
"""
from builtins import range
from datetime import timedelta, datetime
import dateutil
import dateutil.parser
from io import BytesIO
import json
import logging
import os
import os.path
import requests
import sys
import zipfile

from garminexport.authenticator import (Authenticator,
                                        ensure_authenticated,
                                        require_status)
from garminexport.retryer import (Retryer,
                                  ExponentialBackoffDelayStrategy,
                                  MaxRetriesStopStrategy)
from garminexport.token_store import TokenStore


log = logging.getLogger(__name__)
# reduce logging noise from requests library
logging.getLogger("requests").setLevel(logging.ERROR)


class GarminClient(object):
    """A client class used to authenticate with Garmin Connect and extract data
    from the user account.

    Any client method with the `ensure_authenticated` decorator will make sure
    that the client uses a fresh OAuth token (and session cookies) for
    authentication.

    The connect method can also be called separately to establish an
    authenticated session. This might be useful to verify client credentials in
    isolation.

    When the client is no longer needed the disconnect method should be called
    to reclaim system resources.

    Example of use:

      try:
          client = GarminClient("<username>", "<password>", ".garminexport")
          client.connect()
          ids = client.list_activity_ids()
              for activity_id in ids:
                  gpx = client.get_activity_gpx(activity_id)
      finally:
          client.disconnect()

    """

    def __init__(self, username: str, password: str, auth_token_dir: str):
        """Initialize a :class:`GarminClient` instance.

        :param username: Garmin Connect user name or email address.
        :param password: Garmin Connect account password.
        :param auth_token_dir: Folder where authentication tokens from
          successful logins are stored. If this directory exists and contains a
          sufficiently fresh OAuth token it will be reused. Otherwise a new
          login attempt is made and, if successful, the OAuth token gets
          written to the folder.
        """
        self.authenticator = Authenticator(TokenStore(auth_token_dir),
                                           username, password)
        self.session = None

    def connect(self):
        """Ensures an authenticated Garmin Connect session."""
        if not self.session:
            self.session = self.authenticator.ensure_authenticated_session()

    def disconnect(self):
        """Drops the current session if one is active."""
        if self.session:
            self.session.close()
            self.session = None

    @ensure_authenticated
    def list_activities(self) -> list[(int, datetime)]:
        """Return all activity ids stored by the logged in user, along
        with their starting timestamps.

        :returns: The full list of activity identifiers (along with their
          starting timestamps).
        """
        ids = []
        batch_size = 100
        # fetch in batches since the API doesn't allow more than a certain
        # number of activities to be retrieved on every invocation
        for start_index in range(0, sys.maxsize, batch_size):
            next_batch = self._fetch_activity_ids_and_ts(
                start_index, batch_size)
            if not next_batch:
                break
            ids.extend(next_batch)
        return ids

    @ensure_authenticated
    def _fetch_activity_ids_and_ts(self, start_index, max_limit: int = 100) \
            -> (int, datetime):
        """Return a sequence of activity ids (along with their starting
        timestamps) starting at a given index, with index 0 being the user's
        most recently registered activity.

        Should the index be out of bounds or the account empty, an empty list
        is returned.

        :param start_index: The index of the first activity to retrieve.
        :param max_limit: The (maximum) number of activities to retrieve.

        :returns: A list of activity JSON dicts describing the activity
        """
        log.debug("fetching activities %d through %d ...",
                  start_index, start_index + max_limit - 1)
        response = self.session.get(
            "https://connect.garmin.com/activitylist-service/activities/search/activities",
            params={"start": start_index, "limit": max_limit})
        if response.status_code != 200:
            raise Exception(
                u"failed to fetch activities {} to {} types: {}\n{}".format(
                    start_index, (start_index + max_limit - 1),
                    response.status_code,
                    response.text))
        activities = json.loads(response.text)
        if not activities:
            # index out of bounds or empty account
            return []

        entries = []
        for activity in activities:
            id = int(activity["activityId"])
            timestamp_utc = dateutil.parser.parse(activity["startTimeGMT"])
            # make sure UTC timezone gets set
            timestamp_utc = timestamp_utc.replace(tzinfo=dateutil.tz.tzutc())
            entries.append((id, timestamp_utc))
        log.debug("got %d activities.", len(entries))
        return entries

    @ensure_authenticated
    def get_activity_summary(self, activity_id: int) -> dict:
        """Return a summary about a given activity. The summary contains
        several statistics, such as duration, GPS starting point, GPS end
        point, elevation gain, max heart rate, max pace, max speed, etc).

        :param activity_id: Activity identifier.
        :returns: The activity summary as a JSON dict.

        """
        response = self.session.get(
            "https://connect.garmin.com/activity-service/activity/{}".
            format(activity_id))
        require_status(response, 200)
        return json.loads(response.text)

    @ensure_authenticated
    def get_activity_details(self, activity_id: int) -> dict:
        """Return a JSON representation of a given activity including
        available measurements such as location (longitude, latitude),
        heart rate, distance, pace, speed, elevation.

        :param activity_id: Activity identifier.
        :returns: The activity details as a JSON dict.
        """
        # mounted at xml or json depending on result encoding
        response = self.session.get(
            "https://connect.garmin.com/activity-service/activity/{}/details".
            format(activity_id))
        require_status(response, 200)
        return json.loads(response.text)

    @ensure_authenticated
    def get_activity_gpx(self, activity_id: int) -> str:
        """Return a GPX (GPS Exchange Format) representation of a
        given activity. If the activity cannot be exported to GPX
        (not yet observed in practice, but that doesn't exclude the
        possibility), a :obj:`None` value is returned.

        :param activity_id: Activity identifier.
        :returns: The GPX representation of the activity as an XML string
          or ``None`` if the activity couldn't be exported to GPX.
        """
        response = self.session.get(
            "https://connect.garmin.com/download-service/export/gpx/activity/{}"
            .format(activity_id))
        # An alternate URL that seems to produce the same results
        # and is the one used when exporting through the Garmin
        # Connect web page.
        # response = self.session.get("https://connect.garmin.com/proxy/activity-service-1.1/gpx/activity/{}?full=true".format(activity_id))

        # A 404 (Not Found) or 204 (No Content) response are both indicators
        # of a gpx file not being available for the activity. It may, for
        # example be a manually entered activity without any device data.
        if response.status_code in (404, 204):
            return None
        require_status(response, 200)
        return response.text

    @ensure_authenticated
    def get_activity_tcx(self, activity_id: int) -> str:
        """Return a TCX (Training Center XML) representation of a
        given activity. If the activity doesn't have a TCX source (for
        example, if it was originally uploaded in GPX format, Garmin
        won't try to synthesize a TCX file) a :obj:`None` value is
        returned.

        :param activity_id: Activity identifier.
        :returns: The TCX representation of the activity as an XML string
          or ``None`` if the activity cannot be exported to TCX.
        """

        response = self.session.get(
            "https://connect.garmin.com/download-service/export/tcx/activity/{}"
            .format(activity_id))
        if response.status_code == 404:
            return None
        require_status(response, 200)
        return response.text

    def get_original_activity(self, activity_id: int) -> (str, str):
        """Return the original file that was uploaded for an activity.
        If the activity doesn't have any file source (for example,
        if it was entered manually rather than imported from a Garmin
        device) then :obj:`(None,None)` is returned.

        :param activity_id: Activity identifier.
        :returns: A tuple of the file type (e.g. 'fit', 'tcx', 'gpx') and
          its contents, or :obj:`(None,None)` if no file is found.
        """
        response = self.session.get(
            "https://connect.garmin.com/download-service/files/activity/{}"
            .format(activity_id))
        # A 404 (Not Found) response is a clear indicator of a missing .fit
        # file. As of lately, the endpoint appears to have started to
        # respond with 500 "NullPointerException" on attempts to download a
        # .fit file for an activity without one.
        if response.status_code in [404, 500]:
            # Manually entered activity, no file source available
            return None, None
        require_status(response, 200)

        # return the first entry from the zip archive where the filename is
        # activity_id (should be the only entry!)
        zip_file = zipfile.ZipFile(BytesIO(response.content), mode="r")
        for path in zip_file.namelist():
            fn, ext = os.path.splitext(path)
            if fn.startswith(str(activity_id)):
                return ext[1:], zip_file.open(path).read()
        return None, None

    def get_activity_fit(self, activity_id: int) -> str:
        """Return a FIT representation for a given activity. If the activity
        doesn't have a FIT source (for example, if it was entered manually
        rather than imported from a Garmin device) a :obj:`None` value is
        returned.

        :param activity_id: Activity identifier.
        :type activity_id: int
        :returns: A string with a FIT file for the activity or :obj:`None`
          if no FIT source exists for this activity (e.g., entered manually).
        """
        fmt, orig_file = self.get_original_activity(activity_id)
        # if the file extension of the original activity file isn't 'fit',
        # this activity was uploaded in a different format (e.g. gpx/tcx)
        # and cannot be exported to fit
        return orig_file if fmt == 'fit' else None

    @ensure_authenticated
    def _poll_upload_completion(self, uuid: str, creation_date: str) -> int:
        """Poll for completion of an upload. If Garmin connect returns
        HTTP status 202 ("Accepted") after initial upload, then we must poll
        until the upload has either succeeded or failed. Raises an
        :class:`Exception` if the upload has failed.

        :param uuid: uploadUuid returned on initial upload.
        :param creation_date: creationDate returned from initial upload (e.g.
          "2020-01-01 12:34:56.789 GMT")
        :returns: Garmin's internalId for the newly-created activity, or
          :obj:`None` if upload is still processing.
        """
        response = self.session.get("https://connect.garmin.com/proxy/activity-service/activity/status/{}/{}?_={}".format(
            creation_date[:10], uuid.replace("-",""), int(datetime.now().timestamp() * 1000)), headers={"nk": "NT"})
        if response.status_code == 201 and response.headers["location"]:
            # location should be https://connectapi.garmin.com/activity-service/activity/ACTIVITY_ID
            return int(response.headers["location"].split("/")[-1])
        elif response.status_code == 202:
            return None # still processing
        else:
            response.raise_for_status()

    @ensure_authenticated
    def upload_activity(self, file: str, format: str = None, name: str = None, \
                        description: str = None, activity_type: str = None, \
                        private: bool = None) -> int:
        """Upload a GPX, TCX, or FIT file for an activity.

        :param file: Path or open file
        :param format: File format (gpx, tcx, fit); guessed from file if None.
        :param name: Optional name for the activity on Garmin Connect
        :param description: Optional description for the activity.
        :param activity_type: Optional activityType key (lowercase: e.g.
          running, cycling)
        :param private: If true, then activity will be set as private.
        :returns: ID of the newly-uploaded activity
        """
        if isinstance(file, str):
            file = open(file, "rb")

        # guess file type if unspecified
        fn = os.path.basename(file.name)
        _, ext = os.path.splitext(fn)
        if format is None:
            if ext.lower() in ('.gpx', '.tcx', '.fit'):
                format = ext.lower()[1:]
            else:
                raise Exception(u"could not guess file type for {}".format(fn))

        # upload it
        files = dict(data=(fn, file))
        response = self.session.post("https://connect.garmin.com/proxy/upload-service/upload/.{}".format(format),
                                     files=files, headers={"nk": "NT"})

        # check response and get activity ID
        try:
            j = response.json()["detailedImportResult"]
        except (json.JSONDecodeError, KeyError):
            raise Exception(u"failed to upload {} for activity: {}\n{}".format(
                format, response.status_code, response.text))

        # single activity, immediate success
        if len(j["successes"]) == 1 and len(j["failures"]) == 0:
            activity_id = j["successes"][0]["internalId"]

        # duplicate of existing activity
        elif len(j["failures"]) == 1 and len(j["successes"]) == 0 and response.status_code == 409:
            log.info(u"duplicate activity uploaded, continuing")
            activity_id = j["failures"][0]["internalId"]

        # need to poll until success/failure
        elif len(j["failures"]) == 0 and len(j["successes"]) == 0 and response.status_code == 202:
            retryer = Retryer(
                returnval_predicate=bool,
                delay_strategy=ExponentialBackoffDelayStrategy(initial_delay=timedelta(seconds=1)),
                stop_strategy=MaxRetriesStopStrategy(6), # wait for up to 64 seconds (2**6)
                error_strategy=None
            )
            activity_id = retryer.call(self._poll_upload_completion, j["uploadUuid"]["uuid"], j["creationDate"])

        # don't know how to handle multiple activities
        elif len(j["successes"]) > 1:
            raise Exception(u"uploading {} resulted in multiple activities ({})".format(
                format, len(j["successes"])))

        # all other errors
        else:
            raise Exception(u"failed to upload {} for activity: {}\n{}".format(
                format, response.status_code, j["failures"]))

        # add optional fields
        data = {}
        if name is not None:
            data['activityName'] = name
        if description is not None:
            data['description'] = description
        if activity_type is not None:
            data['activityTypeDTO'] = {"typeKey": activity_type}
        if private:
            data['privacy'] = {"typeKey": "private"}
        if data:
            data['activityId'] = activity_id
            encoding_headers = {"Content-Type": "application/json; charset=UTF-8"}  # see Tapiriik
            response = self.session.put(
                "https://connect.garmin.com/proxy/activity-service/activity/{}".format(activity_id),
                data=json.dumps(data), headers=encoding_headers)
            if response.status_code != 204:
                raise Exception(u"failed to set metadata for activity {}: {}\n{}".format(
                    activity_id, response.status_code, response.text))

        return activity_id
