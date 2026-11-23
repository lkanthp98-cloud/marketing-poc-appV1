"""Private browser sessions for shared-identity Genie conversations; no OAuth data."""
import hashlib
import hmac
import re
import secrets

COOKIE_NAME='marketing_chat_session'
_secret=secrets.token_bytes(32)


def _signature(value):
    return hmac.new(_secret,value.encode(),hashlib.sha256).hexdigest()


def resolve(value):
    if value:
        parts=value.split('.')
        if len(parts)==2 and re.fullmatch(r'[A-Za-z0-9_-]{43}',parts[0]) and re.fullmatch(r'[a-f0-9]{64}',parts[1]) and hmac.compare_digest(_signature(parts[0]),parts[1]):
            return parts[0],value,False
    token=secrets.token_urlsafe(32)
    return token,token+'.'+_signature(token),True
