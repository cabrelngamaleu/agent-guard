import hashlib
import json
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

with open(sys.argv[1], encoding="utf-8") as f:
    pack = json.load(f)

canonical = json.dumps(
    pack["content"], sort_keys=True, ensure_ascii=False, separators=(",", ":")
).encode("utf-8")
digest = hashlib.sha256(canonical).hexdigest()

if digest != pack["sha256"]:
    sys.exit("ÉCHEC : le contenu ne correspond plus à l'empreinte")

try:
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(pack["public_key"])).verify(
        bytes.fromhex(pack["signature"]), bytes.fromhex(digest)
    )
except InvalidSignature:
    sys.exit("ÉCHEC : signature invalide")

print("Dossier authentique : contenu intact et signature valide")
print("Clé publique à comparer avec celle publiée :", pack["public_key"])   