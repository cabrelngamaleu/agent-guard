import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ISSUER = "http://localhost:8080/realms/agent-guard"
WEB_CLIENT = "agent-guard-web"
AGENT_CLIENT = "agent-guard-agent"
COOKIE = "ag_token"

bearer = HTTPBearer(auto_error=False)
jwks = jwt.PyJWKClient(f"{ISSUER}/protocol/openid-connect/certs")


def current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    token = creds.credentials if creds else request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Jeton manquant")
    try:
        key = jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=ISSUER,
            options={"verify_aud": False},
        )
    except Exception:
        raise HTTPException(401, "Jeton invalide ou expiré")
    if claims.get("azp") not in (WEB_CLIENT, AGENT_CLIENT):
        raise HTTPException(401, "Jeton émis pour une autre application")
    return claims


def roles_of(claims: dict) -> list:
    return claims.get("realm_access", {}).get("roles", [])


def require_approver(user: dict = Depends(current_user)) -> str:
    if user.get("azp") != WEB_CLIENT or "approbateur" not in roles_of(user):
        raise HTTPException(403, "Rôle approbateur requis")
    return user["preferred_username"]


def require_agent(user: dict = Depends(current_user)) -> str:
    if user.get("azp") != AGENT_CLIENT or "agent" not in roles_of(user):
        raise HTTPException(403, "Identité d'agent requise")
    return user["azp"]