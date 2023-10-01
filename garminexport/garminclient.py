#! /usr/bin/env python
"""A module for authenticating against and communicating with selected
parts of the Garmin Connect REST API.
"""
from builtins import range
from datetime import timedelta, datetime
import dateutil
import dateutil.parser
from functools import partial, wraps
from io import BytesIO
import json
import logging
import os
import os.path
import requests
import sys
import zipfile

from garminexport.retryer import Retryer, ExponentialBackoffDelayStrategy, MaxRetriesStopStrategy


log = logging.getLogger(__name__)
# reduce logging noise from requests library
logging.getLogger("requests").setLevel(logging.ERROR)


PORTAL_LOGIN_URL = "https://sso.garmin.com/portal/api/login"
"""Garmin Connect's Single-Sign On login URL."""
SSO_LOGIN_URL = "https://sso.garmin.com/sso/login"
"""Garmin Connect's Single-Sign On login URL."""
SSO_SIGNIN_URL = "https://sso.garmin.com/sso/signin"
"""The Garmin Connect Single-Sign On sign-in URL. This is where the login form
gets POSTed."""


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
        self.session = new_http_session()
        self._authenticate()

    def disconnect(self):
        if self.session:
            self.session.close()
            self.session = None

    def _authenticate(self):
        """
        Authenticates using a Garmin Connect username and password.

        The procedure has changed over the years. A good approach for figuring
        it out is to use the browser development tools to trace all requests
        following a sign-in.
        """
        log.info("authenticating user ...")

        auth_ticket_url = self._login(self.username, self.password)
        log.debug("auth ticket url: '%s'", auth_ticket_url)

        self._claim_auth_ticket(auth_ticket_url)

        # we need to touch base with the main page to complete the login ceremony.
        self.session.get('https://connect.garmin.com/modern')
        # This header appears to be needed on subsequent session requests or we
        # end up with a 402 response from Garmin.
        self.session.headers.update({'NK': 'NT'})

    def _login(self, username, password):
        """Logs in with the supplied account credentials.
        The return value is a URL where the created authentication ticket can be claimed.
        For example, "https://connect.garmin.com/modern?ticket=ST-2550833-30KdiEJ3jqvFzLNGi2C7-sso"

        The response message looks typically something like this:
          {
             "serviceURL":"https://connect.garmin.com/modern/",
             "serviceTicketId":"ST-2550833-30KdiEJ3jqvFzLNGi2C7-sso",
             "responseStatus":{"type":"SUCCESSFUL","message":"","httpStatus":"OK"},
             "customerMfaInfo":null,
             "consentTypeList":null
          }
        """
        headers = {
            'authority': 'sso.garmin.com',
            'origin': 'https://sso.garmin.com',
            'referer': 'https://sso.garmin.com/portal/sso/en-US/sign-in?clientId=GarminConnect&service=https%3A%2F%2Fconnect.garmin.com%2Fmodern',
        }
        params = {
            "clientId": "GarminConnect",
            "service": "https://connect.garmin.com/modern/",
            "gauthHost": "https://sso.garmin.com/sso",
        }
        form_data = {'username': username, 'password': password}

        log.info("passing login credentials ...")
        resp = self.session.post(PORTAL_LOGIN_URL, headers=headers, params=params, json=form_data)
        log.debug("got auth response %d: %s", resp.status_code, resp.text)
        if resp.status_code != 200:
            raise ValueError(f'authentication attempt failed with {resp.status_code}: {resp.text}')
        return self._extract_auth_ticket_url(resp.json())

    def _claim_auth_ticket(self, auth_ticket_url):
        # Note: first we bump the login URL.
        p = {
            'clientId': 'GarminConnect',
            'service': 'https://connect.garmin.com/modern/',
            'webhost': 'https://connect.garmin.com',
            'gateway': 'true',
            'generateExtraServiceTicket': 'true',
            'generateTwoExtraServiceTickets': 'true',
        }
        self.session.get(SSO_LOGIN_URL, headers={}, params=p)

        log.info("claiming auth ticket %s ...", auth_ticket_url)
        response = self.session.get(auth_ticket_url)
        if response.status_code != 200:
            raise RuntimeError(
                "auth failure: failed to claim auth ticket: {}: {}\n{}".format(
                    auth_ticket_url, response.status_code, response.text))


    @staticmethod
    def _extract_auth_ticket_url(auth_response):
        """Extracts an authentication ticket URL from the response of an
        authentication form submission. The auth ticket URL is typically
        of form:

          https://connect.garmin.com/modern?ticket=ST-0123456-aBCDefgh1iJkLmN5opQ9R-cas

        :param auth_response: JSON response from a login form submission.
        """
        if auth_response['responseStatus']['type'] == 'INVALID_USERNAME_PASSWORD':
            RuntimeError("authentication failure: did you provide a correct username/password?")
        service_url = auth_response.get('serviceURL')
        auth_ticket = auth_response.get('serviceTicketId')
        if not service_url:
            raise RuntimeError("auth failure: unable to extract serviceURL")
        if not auth_ticket:
            raise RuntimeError("auth failure: unable to extract serviceTicketId")
        auth_ticket_url = service_url.rstrip('/') + '?ticket=' + auth_ticket
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

        :returns: A list of activity JSON dicts describing the activity
        :rtype: tuples of (int, datetime)
        """
        log.debug("fetching activities %d through %d ...", start_index, start_index + max_limit - 1)
        response = self.session.get(
            "https://connect.garmin.com/proxy/activitylist-service/activities/search/activities",
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
        log.debug("got %d activities.", len(entries))
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
            "https://connect.garmin.com/proxy/activity-service/activity/{}".format(activity_id))
        if response.status_code != 200:
            log.error(u"failed to fetch json summary for activity %s: %d\n%s",
                      activity_id, response.status_code, response.text)
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
            "https://connect.garmin.com/proxy/activity-service/activity/{}/details".format(activity_id))
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
            "https://connect.garmin.com/proxy/download-service/export/gpx/activity/{}".format(activity_id))
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
            "https://connect.garmin.com/proxy/download-service/export/tcx/activity/{}".format(activity_id))
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
            "https://connect.garmin.com/proxy/download-service/files/activity/{}".format(activity_id))
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
            if fn.startswith(str(activity_id)):
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
    def _poll_upload_completion(self, uuid, creation_date):
        """Poll for completion of an upload. If Garmin connect returns
        HTTP status 202 ("Accepted") after initial upload, then we must poll
        until the upload has either succeeded or failed. Raises an
        :class:`Exception` if the upload has failed.

        :param uuid: uploadUuid returned on initial upload.
        :type uuid: str
        :param creation_date: creationDate returned from initial upload (e.g.
          "2020-01-01 12:34:56.789 GMT")
        :type creation_date: str
        :returns: Garmin's internalId for the newly-created activity, or
          :obj:`None` if upload is still processing.
        :rtype: int
        """
        response = self.session.get("https://connect.garmin.com/proxy/activity-service/activity/status/{}/{}?_={}".format(
            creation_date[:10], uuid.replace("-",""), int(datetime.now().timestamp()*1000)), headers={"nk": "NT"})
        if response.status_code == 201 and response.headers["location"]:
            # location should be https://connectapi.garmin.com/activity-service/activity/ACTIVITY_ID
            return int(response.headers["location"].split("/")[-1])
        elif response.status_code == 202:
            return None # still processing
        else:
            response.raise_for_status()

    @require_session
    def upload_activity(self, file, format=None, name=None, description=None, activity_type=None, private=None):
        """Upload a GPX, TCX, or FIT file for an activity.

        :param file: Path or open file
        :param format: File format (gpx, tcx, or fit); guessed from filename if :obj:`None`
        :type format: str
        :param name: Optional name for the activity on Garmin Connect
        :type name: str
        :param description: Optional description for the activity on Garmin Connect
        :type description: str
        :param activity_type: Optional activityType key (lowercase: e.g. running, cycling)
        :type activityType: str
        :param private: If true, then activity will be set as private.
        :type private: bool
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


def new_http_session():
    """Returns a requests-compatible HTTP Session.
    See https://requests.readthedocs.io/en/latest/user/advanced/#session-objects.

    By default it uses the requests library to create http sessions. If built with
    the 'impersonate-browser' extra, it will use curl_cffi and a patched libcurl to
    produce identical TLS fingerprints as a real web browsers to circumvent
    Cloudflare's bot protection.
    """
    session_factory_func = requests.session
    try:
        import curl_cffi.requests
        # For supported browsers: see https://github.com/lwthiker/curl-impersonate#supported-browsers
        browser = os.getenv("GARMINEXPORT_IMPERSONATE_BROWSER", "chrome110")
        log.info("using 'curl_cffi' to create HTTP sessions that impersonate web browser '%s' ...", browser)
        session_factory_func = partial(curl_cffi.requests.Session, impersonate=browser)
    except (ImportError):
        pass
    return session_factory_func()
