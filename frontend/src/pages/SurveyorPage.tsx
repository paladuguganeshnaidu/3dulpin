import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { Badge, sourceBadge } from "../components/ui";
import { api } from "../lib/api";
import type { Parcel, Property } from "../lib/types";

interface Candidate {
  footprint_geojson: any;
  method: string;
  confidence: number;
  requires_verification: boolean;
  model_name?: string;
  model_version?: string;
}

export default function SurveyorPage() {
  const [parcels, setParcels] = useState<Parcel[]>([]);
  const [parcelId, setParcelId] = useState("");
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [useCandidate, setUseCandidate] = useState(false);
  const [buildingName, setBuildingName] = useState("");
  const [floors, setFloors] = useState(4);
  const [floorHeight, setFloorHeight] = useState(3);
  const [createdBuilding, setCreatedBuilding] = useState<Property | null>(null);
  const [buildingFloors, setBuildingFloors] = useState<Property[]>([]);
  const [divideFor, setDivideFor] = useState<Record<string, { rooms: number; owners: string }>>({});
  const [msg, setMsg] = useState("");
  const [pending, setPending] = useState<Property[]>([]);
  const [subs, setSubs] = useState<any[]>([]);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    api<{ items: Parcel[] }>("/parcels?limit=100").then((r) => {
      setParcels(r.items);
      if (!parcelId && r.items.length) setParcelId(r.items[0].id);
    });
    api<{ items: Property[] }>("/properties?status=pending_verification&limit=100").then((r) =>
      setPending(r.items.filter((x) => x.source_type === "ai_derived"))
    );
    api<{ items: any[] }>("/workflow/my-submissions").then((r) => setSubs(r.items));
  }, [reload, parcelId]);

  async function suggestBlock() {
    setMsg("");
    setCandidate(null);
    const par = parcels.find((p) => p.id === parcelId);
    if (!par) return setMsg("Pick a parcel first.");
    try {
      const res = await api<Candidate>("/ai/building-footprint", {
        method: "POST",
        body: { points: par.footprint_geojson.coordinates[0] },
      });
      setCandidate(res);
      setUseCandidate(true);
      setMsg(`AI block suggested (${Math.round(res.confidence * 100)}% confidence). Verify and create.`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Suggestion failed");
    }
  }

  function footprintFor(): any {
    if (useCandidate && candidate) return candidate.footprint_geojson;
    const par = parcels.find((p) => p.id === parcelId);
    if (!par) return null;
    const ring = par.footprint_geojson.coordinates[0];
    const cx = ring.reduce((s: number, p: number[]) => s + p[0], 0) / ring.length;
    const cy = ring.reduce((s: number, p: number[]) => s + p[1], 0) / ring.length;
    return {
      type: "Polygon",
      coordinates: [ring.map((p: number[]) => [cx + (p[0] - cx) * 0.9, cy + (p[1] - cy) * 0.9])],
    };
  }

  async function createBuilding() {
    setMsg("");
    const fp = footprintFor();
    if (!fp) return setMsg("Pick a parcel first.");
    const height = floors * floorHeight;
    try {
      const res = await api<any>("/workflow/properties", {
        method: "POST",
        body: {
          property_type: "building",
          parcel_id: parcelId,
          name: buildingName || `Building on ${parcelId}`,
          footprint_geojson: fp,
          zmin: 0,
          zmax: height,
          floors,
          floor_height: floorHeight,
          assisted: useCandidate && !!candidate,
          model_name: candidate?.model_name,
          model_version: candidate?.model_version,
          confidence: candidate?.confidence,
        },
      });
      const building = res.property as Property;
      setCreatedBuilding(building);
      setCandidate(null);
      setUseCandidate(false);
      setBuildingName("");
      await loadFloors(building.id);
      setMsg(`Building created (${height} m). Now divide each floor into rooms.`);
      setReload((n) => n + 1);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Creation failed");
    }
  }

  async function loadFloors(buildingId: string) {
    const children = await api<{ items: Property[] }>(
      `/properties/${encodeURIComponent(buildingId)}/children?child_type=floor`
    );
    setBuildingFloors(children.items);
    const init: Record<string, { rooms: number; owners: string }> = {};
    children.items.forEach((f) => {
      init[f.id] = { rooms: 2, owners: "" };
    });
    setDivideFor(init);
  }

  function updateDivide(floorId: string, patch: Partial<{ rooms: number; owners: string }>) {
    setDivideFor((d) => ({
      ...d,
      [floorId]: { ...(d[floorId] || { rooms: 2, owners: "" }), ...patch },
    }));
  }

  async function divideFloor(floorId: string) {
    setMsg("");
    const cfg = divideFor[floorId] || { rooms: 2, owners: "" };
    const lines = cfg.owners.split("\n").map((s) => s.trim()).filter(Boolean);
    const n = Math.max(1, lines.length || cfg.rooms);
    const rooms = Array.from({ length: n }, (_, i) => {
      const ownerName = lines[i]?.trim() || undefined;
      return {
        name: `${floorId.split("-").pop()}-${i + 1}`,
        ...(ownerName ? { owner_name: ownerName } : {}),
      };
    });
    try {
      const res = await api<any>(`/workflow/properties/${encodeURIComponent(floorId)}/divide`, {
        method: "POST",
        body: { rooms },
      });
      setMsg(`Floor divided into ${res.created_count} room(s).`);
      setReload((n) => n + 1);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Division failed");
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
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-6 p-6 lg:grid-cols-2">
        <section className="rounded border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">
            Building designer (block · floors · rooms · owners)
          </h2>

          <div className="mt-3 space-y-3 text-sm">
            <label className="block text-slate-600">
              Parcel
              <select
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
                value={parcelId}
                onChange={(e) => setParcelId(e.target.value)}
              >
                {parcels.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id}
                  </option>
                ))}
              </select>
            </label>

            <div className="flex items-center gap-2">
              <button className="btn-teal !py-1 text-xs" onClick={suggestBlock}>
                AI suggest building block
              </button>
              {candidate && (
                <span className="text-xs text-slate-500">
                  {candidate.method.replace(/_/g, " ")} ·{" "}
                  {Math.round(candidate.confidence * 100)}% · needs verification
                </span>
              )}
            </div>
            {candidate && (
              <div className="rounded border border-purple-200 bg-purple-50 p-2 text-xs text-purple-800">
                AI-derived block fitted to the parcel border. Verify it matches the
                building border in street view before use.
              </div>
            )}

            <div className="grid grid-cols-3 gap-2">
              <label className="col-span-3 text-slate-600">
                Building name
                <input
                  className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
                  value={buildingName}
                  onChange={(e) => setBuildingName(e.target.value)}
                  placeholder={`Building on ${parcelId}`}
                />
              </label>
              <label className="text-slate-600">
                Floors
                <input
                  type="number"
                  min={1}
                  className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
                  value={floors}
                  onChange={(e) => setFloors(parseInt(e.target.value || "1", 10))}
                />
              </label>
              <label className="text-slate-600">
                Floor height (m)
                <input
                  type="number"
                  min={1.5}
                  step={0.5}
                  className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
                  value={floorHeight}
                  onChange={(e) => setFloorHeight(parseFloat(e.target.value || "3"))}
                />
              </label>
              <div className="flex items-end">
                <button className="btn-primary w-full" onClick={createBuilding}>
                  Create building
                </button>
              </div>
            </div>
          </div>

          {msg && <p className="mt-3 text-xs text-slate-600">{msg}</p>}

          {buildingFloors.length > 0 && (
            <div className="mt-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Floors on {createdBuilding?.name || createdBuilding?.id}
              </h3>
              <ul className="mt-2 space-y-2">
                {buildingFloors.map((f) => {
                  const cfg = divideFor[f.id] || { rooms: 2, owners: "" };
                  return (
                    <li key={f.id} className="rounded border border-slate-200 p-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-slate-700">
                          {f.name} · z {f.zmin}–{f.zmax} m · <code>{f.ulpin}</code>
                        </span>
                        <button className="btn-ghost !py-0.5" onClick={() => divideFloor(f.id)}>
                          Divide into rooms
                        </button>
                      </div>
                      <div className="mt-2 grid grid-cols-2 gap-2">
                        <label className="text-slate-500">
                          Rooms
                          <input
                            type="number"
                            min={1}
                            className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
                            value={cfg.rooms}
                            onChange={(e) =>
                              updateDivide(f.id, { rooms: parseInt(e.target.value || "1", 10) })
                            }
                          />
                        </label>
                        <label className="text-slate-500">
                          Owners (one per line)
                          <textarea
                            rows={2}
                            placeholder="Ananya R&#10;Vikram S"
                            className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
                            value={cfg.owners}
                            onChange={(e) => updateDivide(f.id, { owners: e.target.value })}
                          />
                        </label>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </section>

        <div className="space-y-6">

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

        <section className="rounded border border-slate-200 bg-white p-4">
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
      </div>
    </Layout>
  );
}
