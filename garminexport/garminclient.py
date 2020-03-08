#! /usr/bin/env python
"""A module for authenticating against and communicating with selected
parts of the Garmin Connect REST API.
"""

import json
import logging
import os
import os.path
import re
import sys
import zipfile
from builtins import range
from functools import wraps
from io import BytesIO

import dateutil
import dateutil.parser
import requests

#
# Note: For more detailed information about the API services
# used by this module, log in to your Garmin Connect account
# through the web browser and visit the API documentation page
# for the REST service of interest. For example:
#   https://connect.garmin.com/proxy/activity-service-1.3/index.html
#   https://connect.garmin.com/proxy/activity-search-service-1.2/index.html
#

#
# Other useful references:
#   https://github.com/cpfair/tapiriik/blob/master/tapiriik/services/GarminConnect/garminconnect.py
#   https://forums.garmin.com/showthread.php?72150-connect-garmin-com-signin-question/page2
#

log = logging.getLogger(__name__)

# reduce logging noise from requests library
logging.getLogger("requests").setLevel(logging.ERROR)

SSO_LOGIN_URL = "https://sso.garmin.com/sso/signin"
"""The Garmin Connect Single-Sign On login URL."""


def require_session(client_function):
    """Decorator that is used to annotate :class:`GarminClient`
    methods that need an authenticated session before being called.
    """

    @wraps(client_function)
    def check_session(*args, **kwargs):
        client_object = args[0]
        if not client_object.session:
            raise Exception("Attempt to use GarminClient without being connected. Call connect() before first use.'")
        return client_function(*args, **kwargs)

    return check_session


class GarminClient(object):
    """A client class used to authenticate with Garmin Connect and
    extract data from the user account.

    Since this class implements the context manager protocol, this object
    can preferably be used together with the with-statement. This will
    automatically take care of logging in to Garmin Connect before any
    further interactions and logging out after the block completes or
    a failure occurs.

    Example of use: ::
      with GarminClient("my.sample@sample.com", "secretpassword") as client:
          ids = client.list_activity_ids()
          for activity_id in ids:
               gpx = client.get_activity_gpx(activity_id)

    """

    def __init__(self, username, password):
        """Initialize a :class:`GarminClient` instance.

        :param username: Garmin Connect user name or email address.
        :type username: str
        :param password: Garmin Connect account password.
        :type password: str
        """
        self.username = username
        self.password = password
        self.session = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()

    def connect(self):
        self.session = requests.Session()
        self._authenticate()

    def disconnect(self):
        if self.session:
            self.session.close()
            self.session = None

    def _authenticate(self):
        log.info("authenticating user ...")
        form_data = {
            "username": self.username,
            "password": self.password,
            "embed": "false"
        }
        request_params = {
            "service": "https://connect.garmin.com/modern"
        }
        headers = {'origin': 'https://sso.garmin.com'}
        auth_response = self.session.post(
            SSO_LOGIN_URL, headers=headers, params=request_params, data=form_data)
        log.debug("got auth response: {}".format(auth_response.text))
        if auth_response.status_code != 200:
            raise ValueError("authentication failure: did you enter valid credentials?")
        auth_ticket_url = self._extract_auth_ticket_url(auth_response.text)
        log.debug("auth ticket url: '{}'".format(auth_ticket_url))

        log.info("claiming auth ticket ...")
        response = self.session.get(auth_ticket_url)
        if response.status_code != 200:
            raise RuntimeError(
                "auth failure: failed to claim auth ticket: {}: {}\n{}".format(
                    auth_ticket_url, response.status_code, response.text))

        # appears like we need to touch base with the old API to initiate
        # some form of legacy session. otherwise certain downloads will fail.
        self.session.get('https://connect.garmin.com/legacy/session')

    @staticmethod
    def _extract_auth_ticket_url(auth_response):
        """Extracts an authentication ticket URL from the response of an
        authentication form submission. The auth ticket URL is typically
        of form:

          https://connect.garmin.com/modern?ticket=ST-0123456-aBCDefgh1iJkLmN5opQ9R-cas

        :param auth_response: HTML response from an auth form submission.
        """
        match = re.search(r'response_url\s*=\s*"(https:[^"]+)"', auth_response)
        if not match:
            raise RuntimeError(
                "auth failure: unable to extract auth ticket URL. did you provide a correct username/password?")
        auth_ticket_url = match.group(1).replace("\\", "")
        return auth_ticket_url

    @require_session
    def list_activities(self):
        """Return all activity ids stored by the logged in user, along
        with their starting timestamps.

        :returns: The full list of activity identifiers (along with their starting timestamps).
        :rtype: tuples of (int, datetime)
        """
        ids = []
        batch_size = 100
        # fetch in batches since the API doesn't allow more than a certain
        # number of activities to be retrieved on every invocation
        for start_index in range(0, sys.maxsize, batch_size):
            next_batch = self._fetch_activity_ids_and_ts(start_index, batch_size)
            if not next_batch:
                break
            ids.extend(next_batch)
        return ids

    @require_session
    def _fetch_activity_ids_and_ts(self, start_index, max_limit=100):
        """Return a sequence of activity ids (along with their starting
        timestamps) starting at a given index, with index 0 being the user's
        most recently registered activity.

        Should the index be out of bounds or the account empty, an empty list is returned.

        :param start_index: The index of the first activity to retrieve.
        :type start_index: int
        :param max_limit: The (maximum) number of activities to retrieve.
        :type max_limit: int

        :returns: A list of activity identifiers (along with their starting timestamps).
        :rtype: tuples of (int, datetime)
        """
        log.debug("fetching activities {} through {} ...".format(start_index, start_index + max_limit - 1))
        response = self.session.get(
            "https://connect.garmin.com/modern/proxy/activitylist-service/activities/search/activities",
            params={"start": start_index, "limit": max_limit})
        if response.status_code != 200:
            raise Exception(
                u"failed to fetch activities {} to {} types: {}\n{}".format(
                    start_index, (start_index + max_limit - 1), response.status_code, response.text))
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
        log.debug("got {} activities.".format(len(entries)))
        return entries

    @require_session
    def get_activity_summary(self, activity_id):
        """Return a summary about a given activity.
        The summary contains several statistics, such as duration, GPS starting
        point, GPS end point, elevation gain, max heart rate, max pace, max speed, etc).

        :param activity_id: Activity identifier.
        :type activity_id: int
        :returns: The activity summary as a JSON dict.
        :rtype: dict
        """
        response = self.session.get(
            "https://connect.garmin.com/modern/proxy/activity-service/activity/{}".format(activity_id))
        if response.status_code != 200:
            log.error(u"failed to fetch json summary for activity {}: {}\n{}".format(
                activity_id, response.status_code, response.text))
            raise Exception(u"failed to fetch json summary for activity {}: {}\n{}".format(
                activity_id, response.status_code, response.text))
        return json.loads(response.text)

    @require_session
    def get_activity_details(self, activity_id):
        """Return a JSON representation of a given activity including
        available measurements such as location (longitude, latitude),
        heart rate, distance, pace, speed, elevation.

        :param activity_id: Activity identifier.
        :type activity_id: int
        :returns: The activity details as a JSON dict.
        :rtype: dict
        """
        # mounted at xml or json depending on result encoding
        response = self.session.get(
            "https://connect.garmin.com/modern/proxy/activity-service/activity/{}/details".format(activity_id))
        if response.status_code != 200:
            raise Exception(u"failed to fetch json activityDetails for {}: {}\n{}".format(
                activity_id, response.status_code, response.text))
        return json.loads(response.text)

    @require_session
    def get_activity_gpx(self, activity_id):
        """Return a GPX (GPS Exchange Format) representation of a
        given activity. If the activity cannot be exported to GPX
        (not yet observed in practice, but that doesn't exclude the
        possibility), a :obj:`None` value is returned.

        :param activity_id: Activity identifier.
        :type activity_id: int
        :returns: The GPX representation of the activity as an XML string
          or ``None`` if the activity couldn't be exported to GPX.
        :rtype: str
        """
        response = self.session.get(
            "https://connect.garmin.com/modern/proxy/download-service/export/gpx/activity/{}".format(activity_id))
        # An alternate URL that seems to produce the same results
        # and is the one used when exporting through the Garmin
        # Connect web page.
        # response = self.session.get("https://connect.garmin.com/proxy/activity-service-1.1/gpx/activity/{}?full=true".format(activity_id))

        # A 404 (Not Found) or 204 (No Content) response are both indicators
        # of a gpx file not being available for the activity. It may, for
        # example be a manually entered activity without any device data.
        if response.status_code in (404, 204):
            return None
        if response.status_code != 200:
            raise Exception(u"failed to fetch GPX for activity {}: {}\n{}".format(
                activity_id, response.status_code, response.text))
        return response.text

    @require_session
    def get_activity_tcx(self, activity_id):
        """Return a TCX (Training Center XML) representation of a
        given activity. If the activity doesn't have a TCX source (for
        example, if it was originally uploaded in GPX format, Garmin
        won't try to synthesize a TCX file) a :obj:`None` value is
        returned.

        :param activity_id: Activity identifier.
        :type activity_id: int
        :returns: The TCX representation of the activity as an XML string
          or ``None`` if the activity cannot be exported to TCX.
        :rtype: str
        """

        response = self.session.get(
            "https://connect.garmin.com/modern/proxy/download-service/export/tcx/activity/{}".format(activity_id))
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise Exception(u"failed to fetch TCX for activity {}: {}\n{}".format(
                activity_id, response.status_code, response.text))
        return response.text

    def get_original_activity(self, activity_id):
        """Return the original file that was uploaded for an activity.
        If the activity doesn't have any file source (for example,
        if it was entered manually rather than imported from a Garmin
        device) then :obj:`(None,None)` is returned.

        :param activity_id: Activity identifier.
        :type activity_id: int
        :returns: A tuple of the file type (e.g. 'fit', 'tcx', 'gpx') and
          its contents, or :obj:`(None,None)` if no file is found.
        :rtype: (str, str)
        """
        response = self.session.get(
            "https://connect.garmin.com/modern/proxy/download-service/files/activity/{}".format(activity_id))
        # A 404 (Not Found) response is a clear indicator of a missing .fit
        # file. As of lately, the endpoint appears to have started to
        # respond with 500 "NullPointerException" on attempts to download a
        # .fit file for an activity without one.
        if response.status_code in [404, 500]:
            # Manually entered activity, no file source available
            return None, None
        if response.status_code != 200:
            raise Exception(
                u"failed to get original activity file for {}: {}\n{}".format(
                    activity_id, response.status_code, response.text))

        # return the first entry from the zip archive where the filename is
        # activity_id (should be the only entry!)
        zip_file = zipfile.ZipFile(BytesIO(response.content), mode="r")
        for path in zip_file.namelist():
            fn, ext = os.path.splitext(path)
            if fn == str(activity_id):
                return ext[1:], zip_file.open(path).read()
        return None, None

    def get_activity_fit(self, activity_id):
        """Return a FIT representation for a given activity. If the activity
        doesn't have a FIT source (for example, if it was entered manually
        rather than imported from a Garmin device) a :obj:`None` value is
        returned.

        :param activity_id: Activity identifier.
        :type activity_id: int
        :returns: A string with a FIT file for the activity or :obj:`None`
          if no FIT source exists for this activity (e.g., entered manually).
        :rtype: str
        """
        fmt, orig_file = self.get_original_activity(activity_id)
        # if the file extension of the original activity file isn't 'fit',
        # this activity was uploaded in a different format (e.g. gpx/tcx)
        # and cannot be exported to fit
        return orig_file if fmt == 'fit' else None

    @require_session
    def upload_activity(self, file, format=None, name=None, description=None, activity_type=None, private=None):
        """Upload a GPX, TCX, or FIT file for an activity.

        :param file: Path or open file
        :param format: File format (gpx, tcx, or fit); guessed from filename if None
        :param name: Optional name for the activity on Garmin Connect
        :param description: Optional description for the activity on Garmin Connect
        :param activity_type: Optional activityType key (lowercase: e.g. running, cycling)
        :param private: If true, then activity will be set as private.
        :returns: ID of the newly-uploaded activity
        :rtype: int
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
        response = self.session.post("https://connect.garmin.com/modern/proxy/upload-service/upload/.{}".format(format),
                                     files=files, headers={"nk": "NT"})

        # check response and get activity ID
        try:
            j = response.json()["detailedImportResult"]
        except (json.JSONDecodeError, KeyError):
            raise Exception(u"failed to upload {} for activity: {}\n{}".format(
                format, response.status_code, response.text))

        if len(j["failures"]) or len(j["successes"]) < 1:
            raise Exception(u"failed to upload {} for activity: {}\n{}".format(
                format, response.status_code, j["failures"]))

        if len(j["successes"]) > 1:
            raise Exception(u"uploading {} resulted in multiple activities ({})".format(
                format, len(j["successes"])))

        activity_id = j["successes"][0]["internalId"]

        # add optional fields
        data = {}
        if name is not None:
            data['activityName'] = name
        if description is not None:
            data['description'] = name
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
