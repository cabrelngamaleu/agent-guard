SEUIL_AUTO = 100_000
SEUIL_MAX = 5_000_000


def evaluate(action: str, payload: dict) -> tuple[str, str]:
    """Retourne (décision, motif). Décisions : allow, require_approval, deny."""
    if action == "solde.consulter":
        return "allow", "Lecture seule"
    if action == "virement.execute":
        montant = payload.get("montant")
        if (
            isinstance(montant, bool)
            or not isinstance(montant, (int, float))
            or montant <= 0
        ):
            return "deny", "Montant absent ou invalide"
        if montant <= SEUIL_AUTO:
            return "allow", f"Montant inférieur ou égal à {SEUIL_AUTO}"
        if montant <= SEUIL_MAX:
            return "require_approval", f"Montant supérieur à {SEUIL_AUTO}"
        return "deny", f"Montant supérieur au plafond de {SEUIL_MAX}"
    if action == "acces.reinitialiser":
        return "require_approval", "Action sensible sur les accès"
    return "deny", "Action inconnue : refus par défaut"