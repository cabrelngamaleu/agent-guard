"use client";

import { useCallback, useEffect, useState } from "react";

type ActionRequest = {
  id: number;
  created_at: string;
  agent: string;
  action: string;
  payload: Record<string, unknown>;
  status: string;
  reason: string;
  decided_by: string | null;
  decided_at: string | null;
};

type Integrity = {
  valid: boolean;
  checked: number;
  broken_at_id: number | null;
};

const STATUS: Record<string, { label: string; tone: string }> = {
  allowed: { label: "Autorisée", tone: "ok" },
  approved: { label: "Approuvée", tone: "ok" },
  denied: { label: "Refusée", tone: "bad" },
  rejected: { label: "Rejetée", tone: "bad" },
};

function formatValue(value: unknown): string {
  if (typeof value === "number") return value.toLocaleString("fr-FR");
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Payload({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data);
  if (entries.length === 0) return <span className="muted">—</span>;
  return (
    <dl className="payload">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function Home() {
  const [actions, setActions] = useState<ActionRequest[]>([]);
  const [integrity, setIntegrity] = useState<Integrity | null>(null);
  const [approver, setApprover] = useState("");
  const [error, setError] = useState("");
  const [offline, setOffline] = useState(false);

  const load = useCallback(async () => {
    try {
      const [a, i] = await Promise.all([
        fetch("/api/actions"),
        fetch("/api/audit/verify"),
      ]);
      if (!a.ok || !i.ok) throw new Error("API");
      setActions(await a.json());
      setIntegrity(await i.json());
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load]);

  async function decide(id: number, verb: "approve" | "reject") {
    setError("");
    if (!approver.trim()) {
      setError("Indiquez votre nom avant de décider.");
      return;
    }
    const res = await fetch(`/api/actions/${id}/${verb}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approver: approver.trim() }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      setError(
        typeof data?.detail === "string" ? data.detail : "La décision a échoué."
      );
    }
    await load();
  }

  const pending = actions.filter((a) => a.status === "pending");
  const history = actions.filter((a) => a.status !== "pending");
  const count = (...statuses: string[]) =>
    actions.filter((a) => statuses.includes(a.status)).length;
  const figures: [string, number][] = [
    ["En attente", pending.length],
    ["Autorisées d'office", count("allowed")],
    ["Approuvées", count("approved")],
    ["Refusées ou rejetées", count("denied", "rejected")],
  ];

  return (
    <div className="page">
      <header className="masthead">
        <div>
          <p className="wordmark">Agent Guard</p>
          <h1 className="title">Registre de contrôle des agents IA</h1>
        </div>
        {integrity && (
          <p className={`seal ${integrity.valid ? "ok" : "bad"}`}>
            <span className="dot" />
            {integrity.valid
              ? `Journal intègre · ${integrity.checked} événements`
              : `Journal altéré · événement ${integrity.broken_at_id}`}
          </p>
        )}
      </header>

      {offline && (
        <p className="notice">API injoignable. Vérifiez que le serveur tourne.</p>
      )}
      {error && <p className="notice">{error}</p>}

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
          <h2>En attente de décision</h2>
          <label className="field">
            <span className="label">Approbateur</span>
            <input
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
              placeholder="Votre nom"
            />
          </label>
        </div>
        {pending.length === 0 ? (
          <p className="empty">Aucune demande en attente.</p>
        ) : (
          <ul className="queue">
            {pending.map((a) => (
              <li key={a.id}>
                <span className="num">N° {a.id}</span>
                <div>
                  <p className="action">{a.action}</p>
                  <Payload data={a.payload} />
                  <p className="muted">
                    {a.reason} · demandé par {a.agent} ·{" "}
                    {formatTime(a.created_at)}
                  </p>
                </div>
                <div className="buttons">
                  <button
                    className="primary"
                    onClick={() => decide(a.id, "approve")}
                  >
                    Approuver
                  </button>
                  <button onClick={() => decide(a.id, "reject")}>Rejeter</button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <div className="section-head">
          <h2>Registre</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>N°</th>
                <th>Action</th>
                <th>Détail</th>
                <th>Agent</th>
                <th>Statut</th>
                <th>Décidé par</th>
                <th>Horodatage</th>
              </tr>
            </thead>
            <tbody>
              {history.map((a) => {
                const s = STATUS[a.status] ?? { label: a.status, tone: "" };
                return (
                  <tr key={a.id}>
                    <td className="mono">{a.id}</td>
                    <td className="mono">{a.action}</td>
                    <td>
                      <Payload data={a.payload} />
                    </td>
                    <td>{a.agent}</td>
                    <td>
                      <span className={`status ${s.tone}`}>
                        <span className="dot" />
                        {s.label}
                      </span>
                      <p className="muted">{a.reason}</p>
                    </td>
                    <td>{a.decided_by ?? "—"}</td>
                    <td className="mono">
                      {formatTime(a.decided_at ?? a.created_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <footer className="colophon">
        Chaque décision est inscrite dans un journal chaîné par SHA-256.
      </footer>
    </div>
  );
}