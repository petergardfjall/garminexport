from collections.abc import Callable
import garth
import logging
from functools import wraps
import requests
import requests.sessions
from requests.sessions import Session

from garminexport.token_store import TokenStore, time_to_expiry
from garth.auth_tokens import OAuth1Token, OAuth2Token

log = logging.getLogger(__name__)


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
    """

    def __init__(self, token_store: TokenStore, username: str, password: str,
                 mfa_code_supplier: Callable[[], str] = mfa_code_prompt):
        self.token_store = token_store
        self.username = username
        self.password = password
        self.mfa_code_prompt = mfa_code_prompt

    def ensure_authenticated_session(self) -> Session:
        """Returns a Session prepared with authentication headers."""
        oauth2_token = self._ensure_token()
        # If the token is close to expiry we need to refresh it.
        oauth2_token = self._ensure_fresh(oauth2_token)

        # Prepare an authenticated session with headers.
        authenticated_session = requests.Session()
        authenticated_session.headers.update({
            'Authorization': '{} {}'.format(
                oauth2_token.token_type, oauth2_token.access_token),
            'Di-Backend': 'connectapi.garmin.com',
            'NK': 'NT'})
        return authenticated_session

    def _ensure_token(self) -> OAuth2Token:
        if self.token_store.has_refreshable_token():
            log.debug("has refreshable oauth2 token ...")
            return self.token_store.get_oauth2_token()

        log.debug("no refreshable oauth2 token found, acquiring new ...")
        oauth1_token, oauth2_token = self._acquire_tokens()
        log.debug("saving acquired token in token store ...")
        self._save_tokens(oauth1_token, oauth2_token)
        return oauth2_token

    def _ensure_fresh(self, token: OAuth2Token) -> OAuth2Token:
        if time_to_expiry(token) > 60:
            log.debug("access_token still fresh (expires in %.1fs)",
                      time_to_expiry(token))
            return token
        # Refresh auth token and save in token store.
        log.debug("refreshing oauth2 token (expires in %.1fs) ...",
                  time_to_expiry(token))
        auth_client = garth.Client(
            oauth1_token=self.token_store.get_oauth1_token(),
            oauth2_token=token)
        auth_client.refresh_oauth2()
        log.debug("saving refreshed oauth token ...")
        self._save_tokens(auth_client.oauth1_token, auth_client.oauth2_token)
        return auth_client.oauth2_token

    def _acquire_tokens(self) -> (OAuth1Token, OAuth2Token):
        """Perform full login to acquire both OAuth1Token and OAuth2Token."""
        log.debug("acquiring authentication token ...")
        auth_client = garth.Client()
        oauth1_token, oauth2_token = auth_client.login(
            self.username, self.password, prompt_mfa=self.mfa_code_prompt)
        return oauth1_token, oauth2_token

    def _save_tokens(self, oauth1_token: OAuth1Token,
                     oauth2_token: OAuth2Token):
        """Saves acquired oauth tokens to the TokenStore."""
        self.token_store.set_oauth1_token(oauth1_token)
        self.token_store.set_oauth2_token(oauth2_token)
