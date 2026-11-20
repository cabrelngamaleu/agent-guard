import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ISSUER = "http://localhost:8080/realms/agent-guard"
CLIENT_ID = "agent-guard-web"

bearer = HTTPBearer(auto_error=False)
jwks = jwt.PyJWKClient(f"{ISSUER}/protocol/openid-connect/certs")


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if creds is None:
        raise HTTPException(401, "Jeton manquant")
    try:
        key = jwks.get_signing_key_from_jwt(creds.credentials).key
        claims = jwt.decode(
            creds.credentials,
            key,
            algorithms=["RS256"],
            issuer=ISSUER,
            options={"verify_aud": False},
        )
    except Exception:
        raise HTTPException(401, "Jeton invalide ou expiré")
    if claims.get("azp") != CLIENT_ID:
        raise HTTPException(401, "Jeton émis pour une autre application")
    return claims


def require_approver(user: dict = Depends(current_user)) -> str:
    roles = user.get("realm_access", {}).get("roles", [])
    if "approbateur" not in roles:
        raise HTTPException(403, "Rôle approbateur requis")
    return user["preferred_username"]