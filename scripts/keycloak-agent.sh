#!/usr/bin/env bash
# Ajoute l'identité de l'agent dans Keycloak. À lancer une fois, depuis la racine.
set -euo pipefail
set -a; source .env; set +a

KC="docker compose exec -T keycloak /opt/keycloak/bin/kcadm.sh"

$KC config credentials --server http://localhost:8080 --realm master \
  --user admin --password "$KC_ADMIN_PASSWORD"

$KC update realms/agent-guard -s accessTokenLifespan=900
$KC create roles -r agent-guard -s name=agent
$KC create clients -r agent-guard -s clientId=agent-guard-agent \
  -s publicClient=false -s serviceAccountsEnabled=true \
  -s standardFlowEnabled=false -s directAccessGrantsEnabled=false \
  -s secret="$AGENT_CLIENT_SECRET"
$KC add-roles -r agent-guard \
  --uusername service-account-agent-guard-agent --rolename agent

echo "Identité de l'agent créée."