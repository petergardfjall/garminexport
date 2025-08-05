from collections.abc import Callable
import logging
from functools import wraps
import re
import requests
import requests.sessions
from requests.sessions import Session
from typing import TypeAlias

from garminexport.token_store import JwtFgpCookie
from garminexport.token_store import OAuthToken
from garminexport.token_store import TokenStore

log = logging.getLogger(__name__)

CASTicket: TypeAlias = str
"""A CAS service ticket like "ST-01055566-3753GCopsoOm6yWrrXro-cas"."""

SSO_EMBED_URL = "https://sso.garmin.com/sso/embed"
"""Garmin Connect's single-signon embed URL."""
SSO_SIGNIN_URL = "https://sso.garmin.com/sso/signin"
"""The Garmin Connect single-signon signin URL. This is where the login form
gets POSTed to get a CASTicket."""
OAUTH_EXCHANGE_URL = 'https://connect.garmin.com/modern/di-oauth/exchange'
"""URL to be called once a CAS ticket has been validated to exchange it for an
OAuth token."""

AUTH_TOKEN_REFRESH_URL = \
    "https://connect.garmin.com/services/auth/token/refresh"
"""Expects a POST with input JSON body like {"refresh_token": "eyJyZ..Q=="}.
On success it returns 201 (Created) with an oauth token like below and sets a
JWT_FGP cookie.
{
  "access_token": "<about 1500 characters of base64>",
  "token_type": "bearer",
  "refresh_token": "<about 150 characters of base64>",
  "expires_in": 3599,
  "scope": "..",
  "jti": "81458bbb-c4d9-4fdc-b08c-ac0327f82db9",
  "refresh_token_expires_in": 7199
}
"""

ENTER_MFA_CODE_URL = "https://sso.garmin.com/sso/verifyMFA/loginEnterMfaCode"
"""For users with multi-factor authentication enabled, this is the URL where
the MFA code (sent by Garmin to the user) should be verified."""

SIGNIN_PARAMS = {
    'id':                              'gauth-widget',
    'embedWidget':                     'true',
    'clientId':                        'GarminConnect',
    'gauthHost':                       SSO_EMBED_URL,
    'service':                         SSO_EMBED_URL,
    'source':                          SSO_EMBED_URL,
    'redirectAfterAccountLoginUrl':    SSO_EMBED_URL,
    'redirectAfterAccountCreationUrl': SSO_EMBED_URL}
"""Query parameters to use for login atttempts against SSO_SIGNIN_URL."""


def mfa_code_prompt() -> str:
    """Prompts the user to enter an Multi-Factor Authentication code."""
    return input('Enter MFA code sent to you> ')


def ensure_authenticated(client_function):
    """Decorator that is used to annotate any GarminClient method that needs an
    authenticated session before being called.
    """
    @wraps(client_function)
    def ensure_session(*args, **kwargs):
        """Sets an authenticated session attribute for the calling GarminClient
        object."""
        client_object = args[0]  # The calling GarminClient object.
        # Sanity checks.
        if not hasattr(client_object, 'authenticator'):
            raise Exception('GarminClient missing "authenticator" attribute')
        if not hasattr(client_object, 'session'):
            raise Exception('GarminClient missing "session" attribute')

        # Clean up any prior session.
        if client_object.session:
            client_object.session.close()
        # Ensure an authenticated session prior to making the method call.
        session = client_object.authenticator.ensure_authenticated_session()
        client_object.session = session
        return client_function(*args, **kwargs)

    return ensure_session


class Authenticator(object):
    """Authenticator is intended to be configured for a GarminClient to prepare
    an authenticated session prior to making method calls annotated with the
    `@ensure_authenticated` decorator.

    That will ensure a session is used with with proper headers (notably
    `Authorization`, `Di-Backend`, and `NK`) and cookies (notably `JWT_FGP`).
    """

    def __init__(self, token_store: TokenStore, username: str, password: str,
                 mfa_code_supplier: Callable[[], str] = mfa_code_prompt):
        self.token_store = token_store
        self.username = username
        self.password = password
        self.mfa_code_prompt = mfa_code_prompt

    def ensure_authenticated_session(self) -> Session:
        """Returns a Session with authentication headers and cookies."""
        oauth_tok, jwt_cookie = self._ensure_tokens()
        # If the token is close to expiry we need to refresh it.
        oauth_tok = self._ensure_fresh(oauth_tok, jwt_cookie)

        # Prepare an authenticated session with headers and cookies.
        authenticated_session = requests.Session()
        authenticated_session.headers.update({
            'Authorization': '{} {}'.format(
                oauth_tok.token_type(), oauth_tok.access_token()),
            'Di-Backend': 'connectapi.garmin.com',
            'NK': 'NT'})
        authenticated_session.cookies.set(
            'JWT_FGP', self.token_store.get_jwt_fgp_cookie())
        return authenticated_session

    def _ensure_tokens(self) -> (OAuthToken, JwtFgpCookie):
        if self.token_store.has_fresh_tokens():
            log.debug("reusing existing oauth token found in token store ...")
            return self.token_store.get_oauth_token(), self.token_store.get_jwt_fgp_cookie()

        log.debug("no fresh oauth token found, acquiring new ...")
        oauth_token, jwt_fgp_cookie = self._acquire_tokens()
        # Save in token_store
        log.debug("saving acquired oauth token in token store ...")
        self.token_store.set_oauth_token(oauth_token)
        self.token_store.set_jwt_fgp_cookie(jwt_fgp_cookie)
        return oauth_token, jwt_fgp_cookie

    def _ensure_fresh(self, token: OAuthToken, jwt_cookie: JwtFgpCookie) \
            -> OAuthToken:
        if token.time_to_expiry() > 60:
            log.debug("access_token still fresh (expires in %.1f seconds)",
                      token.time_to_expiry())
            return token
        # Refresh auth token and save in token store.
        log.debug("refreshing oauth token (expires in %.1f seconds) ...",
                  token.time_to_expiry())
        headers = {
            'Authorization': f'{token.token_type()} {token.access_token()}',
            'Di-Backend': 'connectapi.garmin.com',
            'NK': 'NT'}
        resp = requests.post(AUTH_TOKEN_REFRESH_URL,
                             cookies={'JWT_FGP': jwt_cookie}, headers=headers,
                             json={'refresh_token': token.refresh_token()})
        if resp.status_code != 201:
            raise ValueError(f'refresh oauth token: {resp.status_code}: '
                             f'{resp.text}')
        new_token = OAuthToken(resp.json(), age_s=0)
        jwt_fgp_cookie = resp.cookies['JWT_FGP']
        # Save in token store.
        log.debug("saving refreshed oauth token ...")
        self.token_store.set_oauth_token(new_token)
        self.token_store.set_jwt_fgp_cookie(jwt_fgp_cookie)
        return new_token

    def _acquire_tokens(self) -> (OAuthToken, JwtFgpCookie):
        log.debug("acquiring authentication tokens ...")
        auth_client = requests.Session()
        cas_ticket = self._login(auth_client, self.username, self.password)
        log.debug("got CAS ticket: %s", cas_ticket)
        self._validate_cas_ticket(auth_client, cas_ticket)
        return self._fetch_oauth_token(auth_client)

    def _login(self, auth_client: Session, username, password: str) \
            -> CASTicket:
        log.debug("logging in ...")
        # Set cookies.
        log.debug("log in: calling sso/embed to set cookies ...")
        resp = auth_client.get(SSO_EMBED_URL, params={
            'embedWidget': 'true',
            'gauthHost': 'https://sso.garmin.com/sso',
            'id': 'gauth-widget'})
        require_status(resp, 200)
        # Get CSRF token.
        csrf_token = self._get_csrf_token(auth_client)
        # Submit login form
        ticket = self._get_login_auth_ticket(auth_client, csrf_token)
        return ticket

    def _validate_cas_ticket(self, auth_client: Session, ticket: CASTicket):
        """Validates a CAS authentication ticket
        ("ST-01055566-3753GCopsoOm6yWrrXro-cas") granted from a prior login
        form submission."""
        log.debug("validating CAS ticket %s ...", ticket)
        auth_client.get('https://connect.garmin.com/modern/', headers={},
                        params={'ticket': ticket})

    def _fetch_oauth_token(self, auth_client: Session) -> \
            (OAuthToken, JwtFgpCookie):
        log.debug("exchanging CAS ticket for OAuth token ...")
        headers = {
            'authority': 'connect.garmin.com',
            'origin': 'https://connect.garmin.com',
            'referer': 'https://connect.garmin.com/modern/'}
        resp = auth_client.post(OAUTH_EXCHANGE_URL, headers=headers)
        require_status(resp, 200)
        token = OAuthToken(resp.json(), 0)
        return token, auth_client.cookies['JWT_FGP']

    def _get_csrf_token(self, auth_client: Session) -> str:
        resp = auth_client.get(SSO_SIGNIN_URL, params=SIGNIN_PARAMS)
        require_status(resp, 200)
        return find_page_csrf_token(resp.text)

    def _get_login_auth_ticket(self, auth_client: Session, csrf_token: str) \
            -> CASTicket:
        form_data = dict(username=self.username, password=self.password,
                         embed="true", _csrf=csrf_token)
        form_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': SSO_SIGNIN_URL}
        log.debug("using CSRF token for signin page: '%s'", csrf_token)
        resp = auth_client.post(SSO_SIGNIN_URL, headers=form_headers,
                                params=SIGNIN_PARAMS, data=form_data)
        if resp.status_code == 429:
            # CloudFlare blocked us. Retry in one hour.
            raise ValueError(
                'Authentication attempt gave 429 (Too Many Requests). '
                'You are being rate limited. Please back off.')
        title = get_page_title(resp.text)
        log.debug("got login page response:\n%s", resp.text)
        # Note: if the account has multi-factor authentication enabled an MFA
        # code will be sent to the user (as SMS or email, depending on user
        # settings).
        if title == "Enter MFA code for login":
            csrf_token = find_page_csrf_token(resp.text)
            mfa_code = self.mfa_code_prompt()
            log.debug("using CSRF token for mfa verification page: '%s'", csrf_token)
            log.debug("using MFA code: '%s'", csrf_token)
            resp = self._verify_mfa_code(auth_client, csrf_token, mfa_code)
            title = get_page_title(resp.text)
        if title != "Success":
            raise ValueError(f'auth attempt failed with {resp.status_code}: '
                             f'{resp.text}')
        m = re.search(r'ticket=(ST-[^"]+)', resp.text)
        if not m:
            raise ValueError(f'no ticket found in {SSO_SIGNIN_URL} response')
        ticket = m.group(1)
        return ticket

    def _verify_mfa_code(self, auth_client: Session, csrf_token: str,
                         mfa_code: str) -> requests.Response:
        form_data = {"mfa-code": mfa_code, "embed": "true",
                     "_csrf": csrf_token, "fromPage": "setupEnterMfaCode"}
        headers = {'referer': SSO_SIGNIN_URL}
        resp = auth_client.post(ENTER_MFA_CODE_URL, params=SIGNIN_PARAMS,
                                data=form_data, headers=headers)
        log.debug("verify MFA response: %d:\n%s", resp.status_code, resp.text)
        return resp


def require_status(resp: requests.Response, want_code: int):
    """Raises an error unless the response has a given HTTP status code."""
    if resp.status_code != want_code:
        raise ValueError(
            f'{resp.request.method} {resp.request.url} '
            f'gave {resp.status_code} (wanted {want_code}): {resp.text}')


TITLE_RE = re.compile(r"<title>(.+?)</title>")
"""Regular expression used to capture the page title when submitting a login
form to SSO_SIGNIN_URL."""


def get_page_title(html: str) -> str:
    """Retrieve the title element from a HTML page."""
    m = TITLE_RE.search(html)
    if not m:
        raise ValueError("couldn't find page title")
    return m.group(1)


CSRF_RE = re.compile(r'name="_csrf"\s+value="(?P<token>.+?)"')
"""Regular expression used to capture the CSRF token from the SSO_SIGNIN_URL
page."""


def find_page_csrf_token(html: str) -> str:
    m = CSRF_RE.search(html)
    if not m:
        raise ValueError('no CSRF token found in page')
    csrf_token = m.group('token')
    return csrf_token
