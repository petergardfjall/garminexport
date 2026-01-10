from datetime import datetime
import garth
from garth.auth_tokens import OAuth1Token, OAuth2Token
import logging
import os
import os.path

log = logging.getLogger(__name__)


class TokenStore(object):
    """Manages (loads and stores) OAuth tokens needed to authenticate with
    GarminConnect.
    """

    def __init__(self, folder: str):
        self.folder = folder
        self.auth_client = garth.Client()
        os.makedirs(self.folder, mode=0o700, exist_ok=True)

    def has_refreshable_token(self) -> bool:
        """Indicates if the token store has an OAuth2Token with a refresh_token
        that has not expired."""
        try:
            # Try to load saved token.
            oauth2_token = self.get_oauth2_token()
        except Exception:
            return False
        return not oauth2_token.refresh_expired

    def get_oauth1_token(self) -> OAuth1Token:
        """Returns the saved OAuth1Token or throws an exception on failure to
        do so."""
        if self.auth_client.oauth1_token is None:
            self.auth_client.load(self.folder)
        return self.auth_client.oauth1_token

    def get_oauth2_token(self) -> OAuth2Token:
        """Returns the saved OAuth2Token or throws an exception on failure to
        do so."""
        if self.auth_client.oauth2_token is None:
            self.auth_client.load(self.folder)
        return self.auth_client.oauth2_token

    def set_oauth1_token(self, token: OAuth1Token):
        """Stores a new OAuth1Token in the store."""
        self.auth_client.oauth1_token = token
        self.auth_client.dump(self.folder)

    def set_oauth2_token(self, token: OAuth2Token):
        """Stores a new OAuth2Token in the store."""
        self.auth_client.oauth2_token = token
        self.auth_client.dump(self.folder)


def time_to_expiry(token: OAuth2Token) -> float:
    """Time in seconds until the OAuth2Token access_token expires."""
    expire_time = datetime.fromtimestamp(token.expires_at)
    expires_in = (expire_time - datetime.now()).total_seconds()
    return max(0.0, expires_in)


def time_to_refresh_expiry(token: OAuth2Token) -> float:
    """Time in seconds until OAuth2Token refresh_token expires."""
    expire_time = datetime.fromtimestamp(token.refresh_token_expires_at)
    expires_in = (expire_time - datetime.now()).total_seconds()
    return max(0.0, expires_in)
