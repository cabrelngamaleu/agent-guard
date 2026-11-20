from policy import evaluate
from privacy import mask, unmask


def test_refus_par_defaut():
    assert evaluate("base.supprimer", {})[0] == "deny"


def test_seuils_virement():
    assert evaluate("virement.execute", {"montant": 100_000})[0] == "allow"
    assert evaluate("virement.execute", {"montant": 100_001})[0] == "require_approval"
    assert evaluate("virement.execute", {"montant": 5_000_000})[0] == "require_approval"
    assert evaluate("virement.execute", {"montant": 5_000_001})[0] == "deny"


def test_montants_invalides():
    for montant in (None, "50000", -1, 0, True):
        assert evaluate("virement.execute", {"montant": montant})[0] == "deny"


def test_masquage_reversible():
    texte = (
        "Envoie 200000 a jean@exemple.cm, "
        "IBAN CM21 1000 2000 3000 4000 5000 123, tel +237 699 12 34 56"
    )
    masque, table = mask(texte)
    assert "jean@exemple.cm" not in masque
    assert "CM21" not in masque
    assert "+237" not in masque
    assert "200000" in masque
    assert unmask(masque, table) == texte