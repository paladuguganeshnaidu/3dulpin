import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { Badge, sourceBadge } from "../components/ui";
import { api } from "../lib/api";
import type { Parcel, Property } from "../lib/types";

export default function SurveyorPage() {
  const [parcels, setParcels] = useState<Parcel[]>([]);
  const [form, setForm] = useState({
    parcel_id: "",
    property_type: "building",
    name: "",
    zmin: "0",
    zmax: "12",
    inset: true,
  });
  const [msg, setMsg] = useState("");
  const [pending, setPending] = useState<Property[]>([]);
  const [subs, setSubs] = useState<any[]>([]);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    api<{ items: Parcel[] }>("/parcels?limit=100").then((r) => {
      setParcels(r.items);
      if (!form.parcel_id && r.items.length) setForm((f) => ({ ...f, parcel_id: r.items[0].id }));
    });
    api<{ items: Property[] }>("/properties?status=pending_verification&limit=100").then((r) =>
      setPending(r.items.filter((x) => x.source_type === "ai_derived"))
    );
    api<{ items: any[] }>("/workflow/my-submissions").then((r) => setSubs(r.items));
  }, [reload]);

  function shrinkRing(coords: number[][][]): number[][] {
    const ring = coords[0];
    // inset by ~6% towards centroid
    const cx = ring.reduce((s, p) => s + p[0], 0) / ring.length;
    const cy = ring.reduce((s, p) => s + p[1], 0) / ring.length;
    return ring.map((p) => [cx + (p[0] - cx) * 0.92, cy + (p[1] - cy) * 0.92]);
  }

  async function createProperty() {
    setMsg("");
    const par = parcels.find((p) => p.id === form.parcel_id);
    if (!par) return setMsg("Pick a parcel first.");
    const footprint =
      form.property_type === "building" && form.inset
        ? { type: "Polygon", coordinates: [shrinkRing(par.footprint_geojson.coordinates)] }
        : par.footprint_geojson;
    try {
      await api("/workflow/properties", {
        method: "POST",
        body: {
          property_type: form.property_type,
          parcel_id: form.parcel_id,
          name: form.name || `${form.property_type} on ${form.parcel_id}`,
          footprint_geojson: footprint,
          zmin: Number(form.zmin),
          zmax: Number(form.zmax),
        },
      });
      setMsg(`Created ${form.property_type} (draft) on ${form.parcel_id}. Inspect it on the map.`);
      setReload((n) => n + 1);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Creation failed");
    }
  }

  async function verify(id: string) {
    try {
      await api(`/workflow/properties/${encodeURIComponent(id)}/verify`, {
        method: "POST",
        body: { verified: true },
      });
      setReload((n) => n + 1);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Verify failed");
    }
  }

  async function submit(id: string) {
    try {
      await api(`/workflow/properties/${encodeURIComponent(id)}/submit`, {
        method: "POST",
        body: { note: "Submitted by surveyor for admin approval." },
      });
      setReload((n) => n + 1);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Submit failed");
    }
  }

  return (
    <Layout>
      <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 p-6 lg:grid-cols-2">
        <section className="rounded border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">Create 3D property (draft)</h2>
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
            <label className="text-slate-600">
              Parcel
              <select
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
                value={form.parcel_id}
                onChange={(e) => setForm({ ...form, parcel_id: e.target.value })}
              >
                {parcels.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-slate-600">
              Type
              <select
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
                value={form.property_type}
                onChange={(e) => setForm({ ...form, property_type: e.target.value })}
              >
                {["building", "floor", "unit", "basement", "parking", "underground_asset", "volume"].map(
                  (t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  )
                )}
              </select>
            </label>
            <label className="col-span-2 text-slate-600">
              Name
              <input
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder={`e.g. ${form.property_type} on parcel`}
              />
            </label>
            <label className="text-slate-600">
              z min (m)
              <input
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
                value={form.zmin}
                onChange={(e) => setForm({ ...form, zmin: e.target.value })}
              />
            </label>
            <label className="text-slate-600">
              z max (m)
              <input
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
                value={form.zmax}
                onChange={(e) => setForm({ ...form, zmax: e.target.value })}
              />
            </label>
            <label className="col-span-2 flex items-center gap-2 text-slate-600">
              <input
                type="checkbox"
                checked={form.inset}
                onChange={(e) => setForm({ ...form, inset: e.target.checked })}
              />
              Building footprint inset inside parcel (demo)
            </label>
          </div>
          <button className="btn-primary mt-3 w-full" onClick={createProperty}>
            Create draft &amp; run validation
          </button>
          {msg && <p className="mt-2 text-xs text-slate-600">{msg}</p>}
        </section>

        <section className="rounded border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">AI candidates needing verification</h2>
          {pending.length === 0 && (
            <p className="mt-2 text-xs text-slate-500">None pending.</p>
          )}
          <ul className="mt-2 space-y-2">
            {pending.map((p) => {
              const b = sourceBadge(p);
              return (
                <li key={p.id} className="flex items-center justify-between rounded border border-slate-200 p-2 text-sm">
                  <div>
                    <div className="text-slate-700">
                      {p.name}{" "}
                      {p.confidence != null && (
                        <span className="text-xs text-slate-400">
                          {Math.round(p.confidence * 100)}% conf.
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex gap-1">
                      <Badge cls={b.cls}>{b.label}</Badge>
                      <Badge cls="bg-slate-100 text-slate-500 border-slate-200">{p.id}</Badge>
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <button className="btn-ghost !py-0.5 text-xs" onClick={() => verify(p.id)}>
                      Verify
                    </button>
                    <button className="btn-teal !py-0.5 text-xs" onClick={() => submit(p.id)}>
                      Submit
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>

        <section className="rounded border border-slate-200 bg-white p-4 lg:col-span-2">
          <h2 className="text-sm font-semibold text-slate-800">My submissions</h2>
          <table className="mt-2 w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr>
                <th className="py-1">Property</th>
                <th>Status</th>
                <th>Submitted</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {subs.map((s) => (
                <tr key={s.submission_id} className="border-t border-slate-100">
                  <td className="py-1">{s.property?.name || s.property_id}</td>
                  <td>
                    <Badge cls="bg-sky-100 text-sky-700 border-sky-300">{s.status}</Badge>
                  </td>
                  <td>{new Date(s.created_at).toLocaleString()}</td>
                  <td className="text-slate-500">{s.note}</td>
                </tr>
              ))}
              {subs.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-2 text-slate-400">
                    No submissions yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      </div>
    </Layout>
  );
}
