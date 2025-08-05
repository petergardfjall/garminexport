import json
import logging
import os
import os.path
import time
from typing import TypeAlias

log = logging.getLogger(__name__)

JwtFgpCookie: TypeAlias = str
"""A JWT_FGP cookie value like 'e3794fe6-6613-4fde-9a3f-2c90e6912702'."""


class OAuthToken(object):
    """An OAuth1 token.
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

    @staticmethod
    def load(path: str) -> 'OAuthToken':
        """Loads an oauth token from a json file."""
        # Note: we make an assumption that the file was created when the token
        # was acquired and therefore represents its age.
        with open(path) as f:
            age_s = time.time() - os.stat(path).st_mtime
            return OAuthToken(json.load(f), age_s)

    def __init__(self, token: dict, age_s: float):
        self.fields = token
        self.age_s = age_s
        # OAuth token sanity check.
        self._require_field(token, 'access_token')
        self._require_field(token, 'token_type')
        self._require_field(token, 'expires_in')
        self._require_field(token, 'refresh_token')
        self._require_field(token, 'refresh_token_expires_in')

    def token_type(self) -> str:
        """Returns the token type. For example 'Bearer'."""
        return self.fields['token_type']

    def access_token(self) -> str:
        """Access token to be used as 'Authorization: Bearer <access_token>'
        header to authenticate to the service."""
        return self.fields['access_token']

    def refresh_token(self) -> str:
        """Refresh token used to request a new access token when it is has
        expired or is near expiry."""
        return self.fields['refresh_token']

    def is_refresh_token_expired(self) -> bool:
        """Indicates if the refresh_token has expired. If it has expired a new
        OAuthToken needs to be acquired altogether."""
        return self.time_to_refresh_token_expiry() <= 0

    def _require_field(self, token: dict, field: str):
        if field not in token:
            raise ValueError(f'oauth token must have "{field}" field')

    def time_to_expiry(self) -> float:
        """Time in seconds until access_token expires."""
        return max(0.0, self.fields['expires_in'] - self.age_s)

    def time_to_refresh_token_expiry(self) -> float:
        """Time in seconds until refresh_token expires."""
        return max(0.0, self.fields['refresh_token_expires_in'] - self.age_s)


class TokenStore(object):
    """Manages (loads and stores) OAuth token and cookies needed to
    authenticate with GarminConnect."""

    def __init__(self, folder: str):
        self.folder = folder
        self.oauth_token_file = os.path.join(folder, 'oauth_token.json')
        self.jwt_fgp_cookie_file = os.path.join(folder, 'jwt_fgp.cookie')
        os.makedirs(self.folder, mode=0o700, exist_ok=True)

    def has_fresh_tokens(self) -> bool:
        """Returns True if the token store has a fresh OAuthToken (whose
        refresh_token has not expired) and a JWT_FGP cookie, otherwise False.
        """
        # Both OAuth token and cookie are needed for authentication.
        has_oauth_token = os.path.isfile(self.oauth_token_file)
        has_jwt_fgp_cookie = os.path.isfile(self.jwt_fgp_cookie_file)
        if (not has_oauth_token) or (not has_jwt_fgp_cookie):
            return False
        return not self.get_oauth_token().is_refresh_token_expired()

    def set_oauth_token(self, token: OAuthToken):
        """Stores a new OAuthToken in the store."""
        with open(self.oauth_token_file, 'w') as f:
            json.dump(token.fields, f, indent=2)

    def get_oauth_token(self) -> OAuthToken:
        """Loads the OAuthToken from the store."""
        return OAuthToken.load(self.oauth_token_file)

    def get_jwt_fgp_cookie(self) -> JwtFgpCookie:
        """Loads the JWT_FGP cookie from the store."""
        with open(self.jwt_fgp_cookie_file) as f:
            return f.read().strip()

    def set_jwt_fgp_cookie(self, value: JwtFgpCookie):
        """Stores a new JWT_FGP cookie in the store."""
        with open(self.jwt_fgp_cookie_file, 'w') as f:
            f.write(value)
