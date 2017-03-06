#! /usr/bin/env python
"""A module for authenticating against and communicating with selected
parts of the Garmin Connect REST API.
"""

import json
import logging
import os
import re
import requests
from StringIO import StringIO
import sys
import zipfile
import dateutil
import dateutil.parser
import os.path
from functools import wraps

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

SSO_LOGIN_URL = "https://sso.garmin.com/sso/login"
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
        params = {
            "service": "http://connect.garmin.com/post-auth/login",
            "clientId": "GarminConnect",
            "consumeServiceTicket": "false",
            "gauthHost": "https://sso.garmin.com/sso"
        }        
        flow_execution_key = self._get_flow_execution_key(params)
        log.debug("flow execution key: '{}'".format(flow_execution_key))
        validation_url = self._get_auth_ticket(flow_execution_key, params)
        # recently, the validation url has started to escape slash characters
        # (with a backslash). remove any such occurences.
        validation_url = validation_url.replace("\/", "/")
        log.debug("auth ticket validation url: {}".format(validation_url))
        self._validate_auth_ticket(validation_url)

        # Referer seems to be a header that is required by the REST API
        self.session.headers.update({'Referer': "https://some.random.site"})
        
        
        
    def _get_flow_execution_key(self, request_params):
        # The flowExecutionKey is embedded in the
        # https://sso.garmin.com/sso/login response page. For example:
        #   <!-- flowExecutionKey: [e3s1] -->
        log.debug("get flow execution key ...")
        response = self.session.get(SSO_LOGIN_URL, params=request_params)
        if response.status_code != 200:
            raise RuntimeError(
                "auth failure: %s: code %d: %s" %
                (SSO_LOGIN_URL, response.status_code, response.text))
        # extract flowExecutionKey
        match = re.search(r'<!-- flowExecutionKey: \[(\w+)\]', response.text)
        if not match:
            raise RuntimeError(
                "auth failure: unable to extract flowExecutionKey: %s:\n%s" %
                (SSO_LOGIN_URL, response.text))
        flow_execution_key = match.group(1)
        return flow_execution_key

    
    def _get_auth_ticket(self, flow_execution_key, request_params):
        data = {
            "username": self.username, "password": self.password,
            "_eventId": "submit", "embed": "true", "lt": flow_execution_key
        }
        log.debug("single sign-on ...")
        sso_response = self.session.post(
            SSO_LOGIN_URL, params=request_params,
            data=data, allow_redirects=False)
        # response must contain an SSO ticket
        ticket_match = re.search("ticket=([^']+)'", sso_response.text)
        if not ticket_match:
            raise ValueError("auth failure: unable to get auth ticket: "
                             "did you enter valid credentials?")
        ticket = ticket_match.group(1)
        log.debug("SSO ticket: {}".format(ticket))
        # response should contain a URL where auth ticket can be validated
        validation_url = re.search(
            r"response_url\s+=\s+'([^']+)'", sso_response.text)
        validation_url = validation_url.group(1)
        return validation_url

    
    def _validate_auth_ticket(self, validation_url):
        log.debug("validating auth ticket at %s ...", validation_url)
        response = self.session.get(validation_url, allow_redirects=False)

        # It appears as if from this point on, the User-Agent header needs to
        # be set to something similar to the value below for authentication
        # to succeed and for downloads of .fit files to work properly.
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.112 Safari/537.36'
        })

        # we will be redirected several times. just follow through ..
        while response.status_code == 302:
            redirect_url = response.headers['Location']
            log.debug("redirected to: '%s'", redirect_url)
            response = self.session.get(redirect_url, allow_redirects=False)
        
        if response.status_code != 200:
            raise Exception(
                u"auth failure: unable to validate auth ticket: {}:\n{}".format(
                    response.status_code, response.text))

        # auth ticket successfully validated.
        # our client should now have all necessary cookies set.

        # as a final step in the "Garmin login rain dance", it appears
        # as though we need to touch on their legacy session page before
        # being granted access to some api services (such as the
        # activity-search-service).
        self.session.get('https://connect.garmin.com/legacy/session')        

        return
            
        
        
    @require_session
    def list_activities(self):
        """Return all activity ids stored by the logged in user, along
        with their starting timestamps.

        :returns: The full list of activity identifiers.
        :rtype: tuples of (int, datetime)
        """        
        ids = []
        batch_size = 100
        # fetch in batches since the API doesn't allow more than a certain
        # number of activities to be retrieved on every invocation
        for start_index in xrange(0, sys.maxint, batch_size):
            next_batch = self._fetch_activity_ids_and_ts(start_index, batch_size)
            if not next_batch:
                break
            ids.extend(next_batch)
        return ids

    @require_session
    def _fetch_activity_ids_and_ts(self, start_index, max_limit=100):
        """Return a sequence of activity ids starting at a given index,
        with index 0 being the user's most recently registered activity.

        Should the index be out of bounds or the account empty, an empty
        list is returned.
        
        :param start_index: The index of the first activity to retrieve.
        :type start_index: int
        :param max_limit: The (maximum) number of activities to retrieve.     
        :type max_limit: int
        
        :returns: A list of activity identifiers.
        :rtype: list of str
        """
        log.debug("fetching activities {} through {} ...".format(
            start_index, start_index+max_limit-1))
        response = self.session.get(
            "https://connect.garmin.com/proxy/activity-search-service-1.2/json/activities", params={"start": start_index, "limit": max_limit})
        if response.status_code != 200:
            raise Exception(
                u"failed to fetch activities {} to {} types: {}\n{}".format(
                    start_index, (start_index+max_limit-1),
                    response.status_code, response.text))
        results = json.loads(response.text)["results"]
        if not "activities" in results:
            # index out of bounds or empty account
            return []

        entries = [ (int(entry["activity"]["activityId"]),
                     dateutil.parser.parse(entry["activity"]["activitySummary"]["BeginTimestamp"]["value"]))
                    for entry in results["activities"] ]
        log.debug("got {} activities.".format(len(entries)))
        return entries
               
    @require_session        
    def get_activity_summary(self, activity_id):
        """Return a summary about a given activity. The
        summary contains several statistics, such as duration, GPS starting
        point, GPS end point, elevation gain, max heart rate, max pace, max
        speed, etc).

        :param activity_id: Activity identifier.
        :type activity_id: int
        :returns: The activity summary as a JSON dict.
        :rtype: dict
        """
        response = self.session.get("https://connect.garmin.com/modern/proxy/activity-service-1.3/json/activity_embed/{}".format(activity_id))
        if response.status_code != 200:
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
        response = self.session.get("https://connect.garmin.com/modern/proxy/activity-service-1.3/json/activityDetails/{}".format(activity_id))
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
        response = self.session.get("https://connect.garmin.com/modern/proxy/download-service/export/gpx/activity/{}".format(activity_id))
        # An alternate URL that seems to produce the same results
        # and is the one used when exporting through the Garmin
        # Connect web page.
        #response = self.session.get("https://connect.garmin.com/proxy/activity-service-1.1/gpx/activity/{}?full=true".format(activity_id))
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
        
        response = self.session.get("https://connect.garmin.com/modern/proxy/download-service/export/tcx/activity/{}".format(activity_id))
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
        response = self.session.get("https://connect.garmin.com/modern/proxy/download-service/files/activity/{}".format(activity_id))
        if response.status_code == 404:
            # Manually entered activity, no file source available
            return (None,None)
        if response.status_code != 200:
            raise Exception(
                u"failed to get original activity file for {}: {}\n{}".format(
                activity_id, response.status_code, response.text))

        # return the first entry from the zip archive where the filename is
        # activity_id (should be the only entry!)
        zip = zipfile.ZipFile(StringIO(response.content), mode="r")
        for path in zip.namelist():
            fn, ext = os.path.splitext(path)
            if fn==str(activity_id):
                return ext[1:], zip.open(path).read()
        return (None,None)    

        
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
        return orig_file if fmt=='fit' else None

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

        if isinstance(file, basestring):
            file = open(file, "rb")

        # guess file type if unspecified
        fn = os.path.basename(file.name)
        _, ext = os.path.splitext(fn)
        if format is None:
            if ext.lower() in ('.gpx','.tcx','.fit'):
                format = ext.lower()[1:]
            else:
                raise Exception(u"could not guess file type for {}".format(fn))

        # upload it
        files = dict(data=(fn, file))
        response = self.session.post("https://connect.garmin.com/proxy/upload-service-1.1/json/upload/.{}".format(format),
                                     files=files)

        # check response and get activity ID
        if response.status_code != 200:
            raise Exception(u"failed to upload {} for activity: {}\n{}".format(
                format, response.status_code, response.text))

        j = response.json()
        if len(j["detailedImportResult"]["failures"]) or len(j["detailedImportResult"]["successes"])!=1:
            raise Exception(u"failed to upload {} for activity")
        activity_id = j["detailedImportResult"]["successes"][0]["internalId"]

        # add optional fields
        fields = ( ('name',name,("display","value")),
                   ('description',description,("display","value")),
                   ('type',activity_type,("activityType","key")),
                   ('privacy','private' if private else None,("definition","key")) )
        for endpoint, value, path in fields:
            if value is not None:
                response = self.session.post("https://connect.garmin.com/proxy/activity-service-1.2/json/{}/{}".format(endpoint, activity_id),
                                             data={'value':value})
                if response.status_code != 200:
                    raise Exception(u"failed to set {} for activity {}: {}\n{}".format(
                        endpoint, activity_id, response.status_code, response.text))

                j = response.json()
                p0, p1 = path
                if p0 not in j or j[p0][p1] != value:
                    raise Exception(u"failed to set {} for activity {}\n".format(endpoint, activity_id))

        return activity_id
