import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@demo.local");
  const [password, setPassword] = useState("Admin@12345");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/map" replace />;

  const quick: [string, string, string][] = [
    ["Admin", "admin@demo.local", "Admin@12345"],
    ["Surveyor", "surveyor@demo.local", "Survey@12345"],
    ["Viewer", "viewer@demo.local", "Viewer@12345"],
  ];

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      navigate("/map");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-slate-100 p-4">
      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow">
        <h1 className="text-xl font-semibold text-slate-800">India 3D ULPIN</h1>
        <p className="mt-1 text-sm text-slate-500">
          Demo sign in (development credentials only)
        </p>
        <form onSubmit={submit} className="mt-5 space-y-3">
          <input
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <p className="text-sm text-rose-600">{error}</p>}
          <button className="btn-primary w-full justify-center" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <div className="mt-4">
          <p className="mb-1.5 text-xs uppercase tracking-wide text-slate-400">Quick fill</p>
          <div className="grid grid-cols-3 gap-2">
            {quick.map(([label, em, pw]) => (
              <button
                key={label}
                className="btn-ghost !py-1 text-xs"
                onClick={() => {
                  setEmail(em);
                  setPassword(pw);
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <p className="mt-4 text-[11px] leading-relaxed text-slate-400">
          Demonstration dataset — not an official land record. AI-derived geometry
          requires human verification.
        </p>
      </div>
    </div>
  );
}
