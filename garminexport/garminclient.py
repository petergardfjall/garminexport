#! /usr/bin/env python
"""A module for authenticating against and communicating with selected
parts of the Garmin Connect REST API.
"""

import json
import logging
import re
import requests
from StringIO import StringIO
import sys
import zipfile

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


def require_session(client_function):
    """Decorator that is used to annotate :class:`GarminClient`
    methods that need an authenticated session before being called.
    """
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
            "consumeServiceTicket": "false"
        }        
        flow_execution_key = self._get_flow_execution_key(params)
        log.debug("flow execution key: '{}'".format(flow_execution_key))
        validation_url = self._get_auth_ticket(flow_execution_key, params)
        log.debug("auth ticket validation url: {}".format(validation_url))
        self._validate_auth_ticket(validation_url)

        # referer seems to be a header that is required by the REST API
        self.session.headers.update({'Referer': "https://some.random.site"})
        
    def _get_flow_execution_key(self, request_params):
        log.debug("get flow execution key ...")
        response = self.session.get(
            "https://sso.garmin.com/sso/login", params=request_params)
        # parse out flowExecutionKey
        flow_execution_key = re.search(
            r'name="lt"\s+value="([^"]+)"', response.text).groups(1)[0]
        return flow_execution_key

    def _get_auth_ticket(self, flow_execution_key, request_params):
        data = {
            "username": self.username, "password": self.password,
            "_eventId": "submit", "embed": "true", "lt": flow_execution_key
        }
        log.debug("single sign-on ...")
        sso_response = self.session.post(
            "https://sso.garmin.com/sso/login",
            params=request_params, data=data, allow_redirects=False)
        # response must contain an SSO ticket
        ticket_match = re.search("ticket=([^']+)'", sso_response.text)
        if not ticket_match:
            raise ValueError("failed to get authentication ticket: "
                             "did you enter valid credentials?")
        ticket = ticket_match.group(1)
        log.debug("SSO ticket: {}".format(ticket))
        # response should contain a URL where auth ticket can be validated
        validation_url = re.search(
            r"response_url\s+=\s+'([^']+)'", sso_response.text)
        validation_url = validation_url.group(1)
        return validation_url

    def _validate_auth_ticket(self, validation_url):
        log.debug("validating authentication ticket ...")
        response = self.session.get(validation_url, allow_redirects=True)
        if not response.status_code == 200:
            raise Exception(
                u"failed to validate authentication ticket: {}:\n{}".format(
                    response.status_code, response.text))
        
        
    @require_session
    def list_activity_ids(self):
        """Return all activity ids stored by the logged in user.

        :returns: The full list of activity identifiers.
        :rtype: list of str
        """        
        ids = []
        batch_size = 100
        # fetch in batches since the API doesn't allow more than a certain
        # number of activities to be retrieved on every invocation
        for start_index in xrange(0, sys.maxint, batch_size):
            next_batch = self._fetch_activity_ids(start_index, batch_size)
            if not next_batch:
                break
            ids.extend(next_batch)
        return ids

    @require_session
    def _fetch_activity_ids(self, start_index, max_limit=100):
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
        log.info("fetching activities {} through {} ...".format(start_index, start_index+max_limit-1))
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
        entries = [int(entry["activity"]["activityId"]) for entry in results["activities"]]
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
        response = self.session.get("https://connect.garmin.com/proxy/activity-service-1.3/json/activity/{}".format(activity_id))
        if response.status_code != 200:
            raise Exception(u"failed to fetch activity {}: {}\n{}".format(
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
        response = self.session.get("https://connect.garmin.com/proxy/activity-service-1.3/json/activityDetails/{}".format(activity_id))
        if response.status_code != 200:
            raise Exception(u"failed to fetch activity details for {}: {}\n{}".format(
                activity_id, response.status_code, response.text))        
        return json.loads(response.text)

    @require_session        
    def get_activity_gpx(self, activity_id):
        """Return a GPX (GPS Exchange Format) representation of a
        given activity.

        :param activity_id: Activity identifier.
        :type activity_id: int
        :returns: The GPX representation of the activity as an XML string.
        :rtype: str
        """
        response = self.session.get("https://connect.garmin.com/proxy/activity-service-1.3/gpx/course/{}".format(activity_id))
        # An alternate URL that seems to produce the same results
        # and is the one used when exporting through the Garmin
        # Connect web page.
        #response = self.session.get("https://connect.garmin.com/proxy/activity-service-1.1/gpx/activity/{}?full=true".format(activity_id))
        if response.status_code != 200:
            raise Exception(u"failed to fetch GPX for activity {}: {}\n{}".format(
                activity_id, response.status_code, response.text))        
        return response.text


    def get_activity_tcx(self, activity_id):
        """Return a TCX (Training Center XML) representation of a
        given activity.

        :param activity_id: Activity identifier.
        :type activity_id: int
        :returns: The TCX representation of the activity as an XML string.
        :rtype: str
        """
        response = self.session.get("https://connect.garmin.com/proxy/activity-service-1.3/tcx/course/{}".format(activity_id))
        if response.status_code != 200:
            raise Exception(u"failed to fetch TCX for activity {}: {}\n{}".format(
                activity_id, response.status_code, response.text))        
        return response.text

    def get_activity_fit(self, activity_id):
        """Return a FIT representation for a given activity.

        :param activity_id: Activity identifier.
        :type activity_id: int
        :returns: A string with a FIT file for the activity.
        :rtype: str
        """
        
        response = self.session.get("https://connect.garmin.com/proxy/download-service/files/activity/{}".format(activity_id))
        if response.status_code != 200:
            raise Exception(u"failed to fetch FIT for activity {}: {}\n{}".format(
                activity_id, response.status_code, response.text))
        # fit file returned from server is in a zip archive
        zipped_fit_file = response.content
        zip = zipfile.ZipFile(StringIO(zipped_fit_file), mode="r")
        # return the "<activity-id>.fit" entry from the zip archive
        return zip.open(str(activity_id) + ".fit").read()
