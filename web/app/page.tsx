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

const BADGE: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  allowed: "bg-green-100 text-green-800",
  approved: "bg-green-100 text-green-800",
  denied: "bg-red-100 text-red-800",
  rejected: "bg-red-100 text-red-800",
};

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

  return (
    <main className="min-h-screen bg-white text-slate-900">
      <div className="mx-auto max-w-4xl p-6">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-bold">Agent Guard</h1>
          {integrity && (
            <span
              className={`rounded-full px-3 py-1 text-sm font-medium ${
                integrity.valid
                  ? "bg-green-100 text-green-800"
                  : "bg-red-100 text-red-800"
              }`}
            >
              {integrity.valid
                ? `Journal intègre (${integrity.checked} événements)`
                : `Journal altéré à l'événement ${integrity.broken_at_id}`}
            </span>
          )}
        </header>

        {offline && (
          <p className="mb-4 rounded bg-red-50 p-3 text-sm text-red-700">
            API injoignable : vérifiez que uvicorn tourne.
          </p>
        )}
        {error && (
          <p className="mb-4 rounded bg-red-50 p-3 text-sm text-red-700">
            {error}
          </p>
        )}

        <label className="mb-6 block text-sm font-medium">
          Votre nom (approbateur)
          <input
            value={approver}
            onChange={(e) => setApprover(e.target.value)}
            className="mt-1 block w-64 rounded border border-slate-300 px-3 py-2"
            placeholder="cabrel"
          />
        </label>

        <h2 className="mb-3 text-lg font-semibold">
          Demandes en attente ({pending.length})
        </h2>
        {pending.length === 0 && (
          <p className="mb-6 text-sm text-slate-500">Aucune demande en attente.</p>
        )}
        <ul className="mb-8 space-y-3">
          {pending.map((a) => (
            <li key={a.id} className="rounded border border-slate-200 p-4">
              <p className="font-medium">
                #{a.id} · {a.action} · demandé par {a.agent}
              </p>
              <p className="mt-1 font-mono text-sm text-slate-600">
                {JSON.stringify(a.payload)}
              </p>
              <p className="mt-1 text-sm text-slate-600">Motif : {a.reason}</p>
              <div className="mt-3 flex gap-2">
                <button
                  onClick={() => decide(a.id, "approve")}
                  className="rounded bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700"
                >
                  Approuver
                </button>
                <button
                  onClick={() => decide(a.id, "reject")}
                  className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
                >
                  Rejeter
                </button>
              </div>
            </li>
          ))}
        </ul>

        <h2 className="mb-3 text-lg font-semibold">Historique</h2>
        <ul className="space-y-2">
          {history.map((a) => (
            <li
              key={a.id}
              className="flex flex-wrap items-center gap-2 rounded border border-slate-200 p-3 text-sm"
            >
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  BADGE[a.status] ?? "bg-slate-100 text-slate-700"
                }`}
              >
                {a.status}
              </span>
              <span className="font-medium">
                #{a.id} · {a.action}
              </span>
              <span className="text-slate-600">
                {a.agent} · {a.reason}
                {a.decided_by ? ` · décidé par ${a.decided_by}` : ""}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}