#!/usr/bin/env bash
# Configure le royaume Keycloak de développement. À lancer une fois, depuis la racine.
set -euo pipefail
set -a; source .env; set +a

KC="docker compose exec -T keycloak /opt/keycloak/bin/kcadm.sh"

$KC config credentials --server http://localhost:8080 --realm master \
  --user admin --password "$KC_ADMIN_PASSWORD"

$KC create realms -s realm=agent-guard -s enabled=true
$KC create roles -r agent-guard -s name=approbateur
$KC create clients -r agent-guard -s clientId=agent-guard-web \
  -s publicClient=true -s directAccessGrantsEnabled=true -s standardFlowEnabled=false

create_user() {
  $KC create users -r agent-guard -s username="$1" -s enabled=true \
    -s email="$1@example.com" -s emailVerified=true -s firstName="$1" -s lastName=Demo
  $KC set-password -r agent-guard --username "$1" --new-password "$KC_USER_PASSWORD"
}

create_user cabrel
create_user stagiaire
$KC add-roles -r agent-guard --uusername cabrel --rolename approbateur

echo "Keycloak configuré."