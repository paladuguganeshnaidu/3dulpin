import { useCallback, useEffect, useState } from "react";
import Layout from "../components/Layout";
import { Badge } from "../components/ui";
import { api } from "../lib/api";

export default function AdminPage() {
  const [stats, setStats] = useState<any>(null);
  const [subs, setSubs] = useState<any[]>([]);
  const [audit, setAudit] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [busy, setBusy] = useState("");
  const [reload, setReload] = useState(0);

  const load = useCallback(async () => {
    try {
      setStats(await api<any>("/admin/stats"));
      const s = await api<any>("/admin/submissions");
      setSubs(s.items);
      setAudit((await api<any>("/audit?limit=12")).items);
      setUsers((await api<any>("/admin/users")).items);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, reload]);

  async function review(id: number, action: string) {
    setBusy(`${action}-${id}`);
    try {
      await api(`/admin/submissions/${id}/review`, { method: "POST", body: { action } });
      setReload((n) => n + 1);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Review failed");
    } finally {
      setBusy("");
    }
  }

  const cards = [
    ["Parcels", stats?.parcels],
    ["Properties", stats?.properties],
    ["Buildings", stats?.buildings],
    ["Floors", stats?.floors],
    ["Units", stats?.units],
    ["Users", stats?.users],
    ["Pending submissions", stats?.submissions_pending],
    ["AI predictions", stats?.ai_predictions],
  ];

  return (
    <Layout>
      <div className="mx-auto max-w-6xl p-6">
        <h1 className="text-lg font-semibold text-slate-800">Admin</h1>
        <p className="text-sm text-slate-500">
          Review submissions, inspect conflicts and audit history.
          {stats?.latest_validation?.state && (
            <span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs">
              Latest global validation:{" "}
              <b className={stats.latest_validation.state === "PASS" ? "text-emerald-600" : "text-rose-600"}>
                {stats.latest_validation.state}
              </b>
            </span>
          )}
        </p>

        <div className="mt-4 grid grid-cols-4 gap-3">
          {cards.map(([label, value]) => (
            <div key={String(label)} className="rounded border border-slate-200 bg-white p-3">
              <div className="text-2xl font-semibold text-ulpin-navy">{value ?? "…"}</div>
              <div className="text-xs text-slate-500">{label}</div>
            </div>
          ))}
        </div>

        <section className="mt-6 rounded border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">Pending submissions</h2>
          {subs.length === 0 && <p className="mt-2 text-xs text-slate-500">Nothing pending.</p>}
          <ul className="mt-2 space-y-2">
            {subs.map((s) => (
              <li
                key={s.submission_id}
                className="flex items-center justify-between rounded border border-slate-200 p-3 text-sm"
              >
                <div>
                  <div className="font-medium text-slate-700">
                    {s.property?.name || s.property_id}{" "}
                    <span className="text-xs text-slate-400">
                      ({s.property?.property_type})
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <Badge cls="bg-sky-100 text-sky-700 border-sky-300">{s.status}</Badge>
                    <span>3D ULPIN: {s.property?.ulpin || "—"}</span>
                    <span>Source: {s.property?.source_type}</span>
                  </div>
                  <div className="mt-1 text-xs text-slate-400">{s.note}</div>
                </div>
                <div className="flex gap-2">
                  <button
                    className="btn-primary !py-1 text-xs"
                    disabled={!!busy}
                    onClick={() => review(s.submission_id, "approve")}
                  >
                    Approve
                  </button>
                  <button
                    className="btn-ghost !py-1 text-xs text-amber-700"
                    disabled={!!busy}
                    onClick={() => review(s.submission_id, "return")}
                  >
                    Return
                  </button>
                  <button
                    className="btn-ghost !py-1 text-xs text-rose-700"
                    disabled={!!busy}
                    onClick={() => review(s.submission_id, "reject")}
                  >
                    Reject
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <section className="rounded border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-800">Recent audit log</h2>
            <table className="mt-2 w-full text-left text-xs">
              <thead className="text-slate-500">
                <tr>
                  <th className="py-1">Action</th>
                  <th>Target</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((a) => (
                  <tr key={a.id} className="border-t border-slate-100">
                    <td className="py-1 font-medium text-slate-600">{a.action}</td>
                    <td className="text-slate-500">
                      {a.target_type}: {a.target_id}
                    </td>
                    <td className="text-slate-400">{new Date(a.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="rounded border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-800">Users</h2>
            <table className="mt-2 w-full text-left text-xs">
              <thead className="text-slate-500">
                <tr>
                  <th className="py-1">Username</th>
                  <th>Email</th>
                  <th>Role</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-t border-slate-100">
                    <td className="py-1">{u.username}</td>
                    <td className="text-slate-500">{u.email}</td>
                    <td className="capitalize">{u.role}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      </div>
    </Layout>
  );
}
