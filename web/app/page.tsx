"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

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

type User = { username: string; roles: string[] };

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
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [actions, setActions] = useState<ActionRequest[]>([]);
  const [integrity, setIntegrity] = useState<Integrity | null>(null);
  const [error, setError] = useState("");
  const [offline, setOffline] = useState(false);

  const load = useCallback(async () => {
    try {
      const me = await fetch("/api/me");
      if (me.status === 401) {
        setUser(null);
        setOffline(false);
        return;
      }
      if (!me.ok) throw new Error("API");
      setUser(await me.json());
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
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load]);

  async function login(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    const form = new FormData(e.currentTarget);
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: form.get("username"),
        password: form.get("password"),
      }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      setError(
        typeof data?.detail === "string" ? data.detail : "Connexion impossible."
      );
      return;
    }
    await load();
  }

  async function logout() {
    await fetch("/auth/logout", { method: "POST" });
    setUser(null);
    setError("");
  }

  async function decide(id: number, verb: "approve" | "reject") {
    setError("");
    const res = await fetch(`/api/actions/${id}/${verb}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      setError(
        typeof data?.detail === "string" ? data.detail : "La décision a échoué."
      );
    }
    await load();
  }

  const canDecide = user?.roles.includes("approbateur") ?? false;
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
        {user && (
          <div className="masthead-side">
            {integrity && (
              <p className={`seal ${integrity.valid ? "ok" : "bad"}`}>
                <span className="dot" />
                {integrity.valid
                  ? `Journal intègre · ${integrity.checked} événements`
                  : `Journal altéré · événement ${integrity.broken_at_id}`}
              </p>
            )}
            <div className="session">
              <span>
                {user.username} · {canDecide ? "approbateur" : "lecture seule"}
              </span>
               <a className="navlink" href="/rapport">Dossier de preuves</a>
              <button className="link" onClick={logout}>
                Se déconnecter
              </button>
            </div>
          </div>
        )}
      </header>

      {offline && (
        <p className="notice">API injoignable. Vérifiez que le serveur tourne.</p>
      )}
      {error && <p className="notice">{error}</p>}

      {ready && !user && !offline && (
        <form className="login" onSubmit={login}>
          <h2>Connexion</h2>
          <label>
            <span className="label">Identifiant</span>
            <input name="username" autoComplete="username" required />
          </label>
          <label>
            <span className="label">Mot de passe</span>
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          <button className="primary" type="submit">
            Se connecter
          </button>
        </form>
      )}

      {user && (
        <>
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
                    {canDecide ? (
                      <div className="buttons">
                        <button
                          className="primary"
                          onClick={() => decide(a.id, "approve")}
                        >
                          Approuver
                        </button>
                        <button onClick={() => decide(a.id, "reject")}>
                          Rejeter
                        </button>
                      </div>
                    ) : (
                      <span className="muted">Lecture seule</span>
                    )}
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
        </>
      )}
    </div>
  );
}