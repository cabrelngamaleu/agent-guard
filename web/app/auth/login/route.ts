import { NextResponse } from "next/server";

const TOKEN_URL =
  "http://localhost:8080/realms/agent-guard/protocol/openid-connect/token";

export async function POST(request: Request) {
  const { username, password } = await request.json().catch(() => ({}));
  if (typeof username !== "string" || typeof password !== "string") {
    return NextResponse.json({ detail: "Identifiants manquants" }, { status: 400 });
  }
  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "password",
      client_id: "agent-guard-web",
      username,
      password,
    }),
    cache: "no-store",
  });
  if (!res.ok) {
    return NextResponse.json(
      { detail: "Identifiant ou mot de passe incorrect" },
      { status: 401 }
    );
  }
  const data = await res.json();
  const response = NextResponse.json({ ok: true });
  response.cookies.set("ag_token", data.access_token, {
    httpOnly: true,
    secure: true,
    sameSite: "strict",
    path: "/",
    maxAge: data.expires_in,
  });
  return response;
}