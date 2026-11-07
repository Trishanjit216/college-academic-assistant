"""JWT authentication that also checks the session stamp (see session_stamp.py).
Tokens issued before this existed carry no stamp, so those users are asked to log in once more."""
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from .session_stamp import CLAIM, stamp


class StampedJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if validated_token.get(CLAIM) != stamp(user):
            raise AuthenticationFailed("Your session has ended. Please log in again.", code="session_ended")
        return user
