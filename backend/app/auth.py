import jwt
import requests

from fastapi import Header, HTTPException, Query

from .config import get_settings

_jwks_cache = None


def get_jwks():
    global _jwks_cache

    if _jwks_cache is None:
        clerk_domain = get_settings().clerk_domain
        jwks_url = f"https://{clerk_domain}/.well-known/jwks.json"
        _jwks_cache = requests.get(jwks_url, timeout=10).json()

    return _jwks_cache


def _verify_token(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
        kid = header["kid"]
        jwks = get_jwks()

        key = next(
            (k for k in jwks["keys"] if k["kid"] == kid),
            None,
        )

        if not key:
            raise HTTPException(status_code=401, detail="Signing key not found")

        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)

        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")

    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    return _verify_token(authorization.split(" ")[1])


async def get_current_user_sse(
    authorization: str = Header(None),
    token: str | None = Query(None),
):
    """Auth for SSE endpoints — EventSource cannot send headers, so the
    JWT is accepted as a ?token= query parameter as a fallback."""
    bearer = None
    if authorization and authorization.startswith("Bearer "):
        bearer = authorization.split(" ")[1]
    elif token:
        bearer = token

    if not bearer:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    return _verify_token(bearer)