"use client";

import { useState } from "react";

type Decision = {
  id: number;
  created_at: string;
  agent: string;
  action: string;
  status: string;
  reason: string;
  decided_by: string | null;
  decided_at: string | null;
};

type Checkpoint = {
  created_at: string;
  sealed_by: string;
  last_id: number;
  last_hash: string;
};

type Pack = {
  content: {
    generated_at: string;
    generated_by: string;
    integrity: {
      valid: boolean;
      checked: number;
      broken_at_id: number | null;
      sealed_until: number | null;
    };
    policy: { seuil_approbation: number; plafond: number };
    summary: {
      total: number;
      by_status: Record<string, number>;
      human_decisions: number;
      invalid_agent_outputs: number;
    };
    decisions: Decision[];
    checkpoints: Checkpoint[];
  };
  sha256: string;
  signature: string;
  public_key: string;
};

const STATUS: Record<string, { label: string; tone: string }> = {
  pending: { label: "En attente", tone: "warn" },
  allowed: { label: "Autorisée", tone: "ok" },
  approved: { label: "Approuvée", tone: "ok" },
  denied: { label: "Refusée", tone: "bad" },
  rejected: { label: "Rejetée", tone: "bad" },
};

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function download(pack: Pack) {
  const blob = new Blob([JSON.stringify(pack, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `dossier-preuves-${pack.sha256.slice(0, 8)}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

export default function Rapport() {
  const [pack, setPack] = useState<Pack | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function generate() {
    setError("");
    setBusy(true);
    try {
      const res = await fetch("/api/audit/evidence", { method: "POST" });
      if (res.status === 401) {
        setError(
          "Session absente ou expirée : connectez-vous d'abord sur le registre."
        );
        return;
      }
      if (res.status === 403) {
        setError("Le rôle approbateur est requis pour générer le dossier.");
        return;
      }
      if (!res.ok) throw new Error("API");
      setPack(await res.json());
    } catch {
      setError("API injoignable. Vérifiez que le serveur tourne.");
    } finally {
      setBusy(false);
    }
  }

  const c = pack?.content;
  const figures: [string, number][] = c
    ? [
        ["Demandes traitées", c.summary.total],
        ["Décisions humaines", c.summary.human_decisions],
        ["Refus automatiques", c.summary.by_status.denied ?? 0],
        ["Sorties d'agent invalides", c.summary.invalid_agent_outputs],
      ]
    : [];

  return (
    <div className="page">
      <header className="masthead">
        <div>
          <p className="wordmark">Agent Guard</p>
          <h1 className="title">Dossier de preuves</h1>
        </div>
        <div className="masthead-side no-print">
          <a className="navlink" href="/">
            Retour au registre
          </a>
        </div>
      </header>

      {error && <p className="notice">{error}</p>}

      <div className="toolbar no-print">
        <button className="primary" onClick={generate} disabled={busy}>
          {busy
            ? "Génération…"
            : pack
              ? "Régénérer le dossier"
              : "Générer le dossier"}
        </button>
        {pack && (
          <>
            <button onClick={() => window.print()}>
              Imprimer ou enregistrer en PDF
            </button>
            <button onClick={() => download(pack)}>
              Télécharger le JSON signé
            </button>
          </>
        )}
      </div>

      {pack && c && (
        <>
          <p className="lead">
            Généré le {formatTime(c.generated_at)} par {c.generated_by}.
          </p>

          <section className="figures">
            {figures.map(([label, value]) => (
              <div key={label}>
                <p className="figure">{value}</p>
                <p className="label">{label}</p>
              </div>
            ))}
          </section>

          <section>
            <div className="section-head">
              <h2>Intégrité du journal</h2>
            </div>
            <dl className="kv">
              <div>
                <dt>Chaîne d&apos;audit</dt>
                <dd className={c.integrity.valid ? "ok" : "bad"}>
                  {c.integrity.valid
                    ? `Intègre · ${c.integrity.checked} événements vérifiés`
                    : `Altérée à l'événement ${c.integrity.broken_at_id}`}
                </dd>
              </div>
              <div>
                <dt>Scellé signé</dt>
                <dd>
                  {c.integrity.sealed_until
                    ? `Jusqu'à l'événement ${c.integrity.sealed_until}`
                    : "Aucun scellé valide"}
                </dd>
              </div>
            </dl>
          </section>

          <section>
            <div className="section-head">
              <h2>Règles en vigueur</h2>
            </div>
            <dl className="kv">
              <div>
                <dt>Approbation humaine au-delà de</dt>
                <dd>{c.policy.seuil_approbation.toLocaleString("fr-FR")}</dd>
              </div>
              <div>
                <dt>Plafond absolu</dt>
                <dd>{c.policy.plafond.toLocaleString("fr-FR")}</dd>
              </div>
              <div>
                <dt>Action non prévue</dt>
                <dd>Refus par défaut</dd>
              </div>
            </dl>
          </section>

          <section>
            <div className="section-head">
              <h2>Décisions</h2>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>N°</th>
                    <th>Action</th>
                    <th>Agent</th>
                    <th>Statut</th>
                    <th>Décidé par</th>
                    <th>Horodatage</th>
                  </tr>
                </thead>
                <tbody>
                  {c.decisions.map((d) => {
                    const s = STATUS[d.status] ?? { label: d.status, tone: "" };
                    return (
                      <tr key={d.id}>
                        <td className="mono">{d.id}</td>
                        <td className="mono">{d.action}</td>
                        <td>{d.agent}</td>
                        <td>
                          <span className={`status ${s.tone}`}>
                            <span className="dot" />
                            {s.label}
                          </span>
                          <p className="muted">{d.reason}</p>
                        </td>
                        <td>{d.decided_by ?? "—"}</td>
                        <td className="mono">
                          {formatTime(d.decided_at ?? d.created_at)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <div className="section-head">
              <h2>Scellés</h2>
            </div>
            {c.checkpoints.length === 0 ? (
              <p className="empty">Aucun scellé posé.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Événement</th>
                      <th>Posé par</th>
                      <th>Date</th>
                      <th>Empreinte</th>
                    </tr>
                  </thead>
                  <tbody>
                    {c.checkpoints.map((cp) => (
                      <tr key={`${cp.last_id}-${cp.created_at}`}>
                        <td className="mono">{cp.last_id}</td>
                        <td>{cp.sealed_by}</td>
                        <td className="mono">{formatTime(cp.created_at)}</td>
                        <td className="hash">{cp.last_hash}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section>
            <div className="section-head">
              <h2>Authenticité du dossier</h2>
            </div>
            <dl className="kv">
              <div>
                <dt>Empreinte SHA-256</dt>
                <dd className="hash">{pack.sha256}</dd>
              </div>
              <div>
                <dt>Signature Ed25519</dt>
                <dd className="hash">{pack.signature}</dd>
              </div>
              <div>
                <dt>Clé publique</dt>
                <dd className="hash">{pack.public_key}</dd>
              </div>
            </dl>
          </section>

          <footer className="colophon">
            Les données d&apos;opération (montants, comptes) sont exclues de ce
            dossier. Les empreintes permettent de le rapprocher du journal complet.
          </footer>
        </>
      )}
    </div>
  );
}