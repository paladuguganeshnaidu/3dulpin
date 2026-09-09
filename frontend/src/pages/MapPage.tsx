import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import CesiumMap, { type LayerState } from "../components/CesiumMap";
import Layout from "../components/Layout";
import { Badge, Field, fmt, sourceBadge, statusColor } from "../components/ui";
import { api } from "../lib/api";
import type { AiAnalysis, Parcel, Property, Region, ValidationIssue } from "../lib/types";

interface Selected {
  kind: "parcel" | "property";
  item: Parcel | Property;
}

const LAYER_DEFAULTS: LayerState = {
  parcels: true,
  buildings: true,
  properties: true,
  underground: false,
  conflicts: true,
};

export default function MapPage() {
  const nav = useNavigate();
  const [regions, setRegions] = useState<Region[]>([]);
  const [region, setRegion] = useState<Region | null>(null);
  const [parcels, setParcels] = useState<Parcel[]>([]);
  const [buildings, setBuildings] = useState<Property[]>([]);
  const [volumes, setVolumes] = useState<Property[]>([]);
  const [conflicts, setConflicts] = useState<ValidationIssue[]>([]);
  const [layers, setLayers] = useState<LayerState>(LAYER_DEFAULTS);
  const [selected, setSelected] = useState<Selected | null>(null);
  const [floors, setFloors] = useState<Property[]>([]);
  const [explode, setExplode] = useState(false);
  const [undergroundRaised, setUndergroundRaised] = useState(false);
  const [revision, setRevision] = useState(0);
  const [analysis, setAnalysis] = useState<AiAnalysis | null>(null);
  const [notice, setNotice] = useState("");
  const [placing, setPlacing] = useState(false);
  const [ctx, setCtx] = useState<{ lon: number; lat: number } | null>(null);

  const conflictIds = useMemo(
    () => new Set(conflicts.flatMap((c) => c.object_ids)),
    [conflicts]
  );

  const load = useCallback(async () => {
    try {
      const [r, p, b] = await Promise.all([
        api<Region[]>("/regions"),
        api<{ items: Parcel[] }>("/parcels?limit=1000"),
        api<{ items: Property[] }>("/buildings?limit=5000"),
      ]);
      const all = await api<{ items: Property[] }>("/properties?limit=5000").catch(
        () => ({ items: [] as Property[] })
      );
      setRegions(r);
      setParcels(p.items);
      setBuildings(b.items);
      // volumes = volumetric + underground + basement + parking
      setVolumes(
        all.items.filter((x) =>
          ["volume", "underground_asset", "basement", "parking"].includes(x.property_type)
        )
      );
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Could not load map data");
    }
  }, []);

  const loadConflicts = useCallback(async () => {
    try {
      const res = await api<{ items: ValidationIssue[] }>("/validation/conflicts");
      setConflicts(res.items);
    } catch {
      setConflicts([]);
    }
  }, []);

  useEffect(() => {
    load();
    loadConflicts();
  }, [load, loadConflicts]);

  useEffect(() => {
    setRevision((n) => n + 1);
  }, [
    parcels,
    buildings,
    volumes,
    conflicts,
    floors,
    explode,
    undergroundRaised,
    layers.parcels,
    layers.buildings,
    layers.properties,
    layers.underground,
    layers.conflicts,
  ]);

  async function handlePick(kind: "parcel" | "property", id: string) {
    try {
      if (kind === "property") {
        const detail = await api<Property>(`/properties/${encodeURIComponent(id)}`);
        const parentChildren = detail.children || [];
        setFloors([]);
        setExplode(false);
        if (detail.property_type === "building") {
          const fc = await api<{ items: Property[] }>(
            `/properties/${encodeURIComponent(id)}/children?child_type=floor`
          );
          setFloors(fc.items);
        } else if (parentChildren.length) {
          setFloors(parentChildren.filter((c) => c.property_type === "floor"));
        }
        setSelected({ kind: "property", item: detail });
      } else {
        const detail = await api<Parcel>(`/parcels/${encodeURIComponent(id)}`);
        setFloors([]);
        setSelected({ kind: "parcel", item: detail });
      }
      setRevision((n) => n + 1);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Selection failed");
    }
  }

  async function runAnalysis() {
    setNotice("");
    setAnalysis(null);
    try {
      const res = await api<AiAnalysis>("/ai/analyse", { method: "POST", body: {} });
      setAnalysis(res);
      loadConflicts();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Analysis failed");
    }
  }

  async function autoPlaceBuilding(parcelId: string) {
    setNotice("");
    setPlacing(true);
    try {
      const res = await api<any>("/workflow/buildings/auto-place", {
        method: "POST",
        body: { parcel_id: parcelId },
      });
      setNotice(
        `ML block placed: ${res.building.name} (${Math.round(
          (res.candidate?.confidence || 0) * 100
        )}% confidence, ${res.floors_created?.length || 0} floors). Requires verification.`
      );
      await load();
      await loadConflicts();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Block placement failed");
    } finally {
      setPlacing(false);
    }
  }

  async function autoPlaceAt(lon: number, lat: number) {
    setCtx(null);
    setPlacing(true);
    setNotice("");
    try {
      const res = await api<any>("/workflow/buildings/auto-place", {
        method: "POST",
        body: { center_lon: lon, center_lat: lat },
      });
      // fly to and select the newly mapped block so it renders in full 3D
      setRegion({
        id: "placed:" + res.building.id,
        name: res.building.name,
        kind: "pilot",
        center: res.building.centroid,
        description: res.building.parcel_id || "",
      });
      await handlePick("property", res.building.id);
      setNotice(
        `ML mapped a ${res.floors_created?.length || 0}-floor block here (${Math.round(
          (res.candidate?.confidence || 0) * 100
        )}% confidence). Click it to design floors & rooms.`
      );
      await load();
      await loadConflicts();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "ML block mapping failed");
    } finally {
      setPlacing(false);
    }
  }

  async function handleSearch(q: string) {
    try {
      const res = await api<{ results: { kind: string; item: any }[]; total: number }>(
        `/search?q=${encodeURIComponent(q)}`
      );
      if (res.results.length === 0) {
        setNotice(`No results for "${q}".`);
        return;
      }
      const first = res.results[0];
      if (first.kind === "region") {
        setRegion(first.item as Region);
        setSelected(null);
      } else if (first.kind === "parcel") {
        const par = first.item as Parcel;
        setRegion({
          id: par.id,
          name: par.id,
          kind: "pilot",
          center: par.centroid,
          description: par.locality,
        });
        await handlePick("parcel", par.id);
      } else {
        const prop = first.item as Property;
        await handlePick("property", prop.id);
        nav(`/map`);
      }
      setNotice(`Found ${res.total} result(s).`);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Search failed");
    }
  }

  function viewFull3d(prop: Property) {
    setLayers((s) => ({ ...s, buildings: true, properties: true }));
    setRegion({
      id: `property-view-${prop.id}`,
      name: prop.name || prop.id,
      kind: "pilot",
      center: prop.centroid,
      description: "Focused 3D building view",
    });
    setExplode(false);
    setRevision((n) => n + 1);
  }

  const selP = selected?.kind === "property" ? (selected.item as Property) : null;
  const selPar = selected?.kind === "parcel" ? (selected.item as Parcel) : null;
  const badge = selP ? sourceBadge(selP) : null;

  return (
    <Layout onSearch={handleSearch}>
      <div className="relative h-full">
        <CesiumMap
          parcels={parcels}
          buildings={buildings}
          volumes={volumes}
          conflictIds={Array.from(conflictIds)}
          layers={layers}
          floors={floors}
          explode={explode}
          undergroundRaised={undergroundRaised}
          region={region}
          revision={revision}
          onPick={handlePick}
          onContext={(pos) => setCtx(pos)}
        />

        {/* Left layer panel */}
        <div className="absolute left-3 top-3 z-10 w-56 rounded border border-slate-200 bg-white/95 p-3 shadow">
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            Region
          </p>
          <div className="mb-3 flex flex-wrap gap-1">
            {regions.map((r) => (
              <button
                key={r.id}
                className={`rounded px-2 py-0.5 text-xs ${
                  region?.id === r.id
                    ? "bg-ulpin-navy text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
                onClick={() => setRegion(r)}
              >
                {r.kind === "pilot" ? "Pilot" : r.name}
              </button>
            ))}
          </div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            Layers
          </p>
          {(
            [
              ["parcels", "Parcels"],
              ["buildings", "Buildings"],
              ["properties", "3D Properties"],
              ["underground", "Underground"],
              ["conflicts", "Conflicts"],
            ] as [keyof LayerState, string][]
          ).map(([key, label]) => (
            <label key={key} className="flex items-center gap-2 py-0.5 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={layers[key]}
                onChange={() => {
                  setLayers((s) => ({ ...s, [key]: !s[key] }));
                  if (key === "underground") setUndergroundRaised(layers[key]);
                }}
              />
              {label}
            </label>
          ))}
          <div className="mt-3 rounded bg-slate-50 p-2 text-[11px] leading-snug text-slate-500">
            Demonstration dataset — not an official land record. AI-derived
            geometry requires human verification.
          </div>
        </div>

        {/* Right info panel */}
        {(selP || selPar) && (
          <div className="absolute right-3 top-3 z-10 w-80 overflow-y-auto rounded border border-slate-200 bg-white/95 p-4 shadow" style={{ maxHeight: "82%" }}>
            <div className="mb-2 flex items-start justify-between gap-2">
              <h2 className="text-sm font-semibold text-slate-800">
                {selP ? selP.name || selP.id : `Parcel ${selPar!.id}`}
              </h2>
              <button
                className="text-slate-400 hover:text-slate-600"
                onClick={() => setSelected(null)}
              >
                ✕
              </button>
            </div>
            {selP && (
              <div className="mb-2 flex flex-wrap gap-1">
                {badge && <Badge cls={badge.cls}>{badge.label}</Badge>}
                <Badge cls={statusColor(selP.status)}>{selP.status.replace(/_/g, " ")}</Badge>
                {selP.property_type === "building" && <Badge cls="bg-sky-100 text-sky-700 border-sky-300">Building</Badge>}
              </div>
            )}
            <div className="mt-2">
              {selP && (
                <>
                  <Field label="3D ULPIN" value={<code className="text-xs">{selP.ulpin || "—"}</code>} />
                  <Field label="Parcel" value={selP.parcel_id} />
                  <Field label="Type" value={selP.property_type} />
                  <Field label="Z min" value={fmt(selP.zmin)} />
                  <Field label="Z max" value={fmt(selP.zmax)} />
                  <Field label="Height" value={selP.height_m != null ? `${fmt(selP.height_m)} m` : "—"} />
                  <Field label="Area" value={selP.area_m2 != null ? `${fmt(selP.area_m2)} m²` : "—"} />
                  <Field label="Volume" value={selP.volume_m3 != null ? `${fmt(selP.volume_m3)} m³` : "—"} />
                  <Field label="Source" value={selP.source_type.replace(/_/g, " ")} />
                  <Field label="Version" value={`V${selP.version}`} />
                  {selP.confidence != null && (
                    <Field label="Confidence" value={`${Math.round(selP.confidence * 100)}%`} />
                  )}
                </>
              )}
              {selPar && (
                <>
                  <Field label="Locality" value={selPar.locality} />
                  <Field label="State / District" value={`${selPar.state_code} / ${selPar.district_code}`} />
                  <Field label="Area" value={`${fmt(selPar.area_m2)} m²`} />
                  <Field label="Properties" value={selPar.property_count} />
                  <button
                    className="btn-teal mt-3 w-full !py-1.5 text-xs"
                    disabled={placing}
                    onClick={() => autoPlaceBuilding(selPar.id)}
                  >
                    {placing ? "Placing with ML…" : "ML: Create building block"}
                  </button>
                  <p className="mt-1 text-[10px] leading-snug text-slate-400">
                    Fits an AI-derived block to the parcel edges, then stacks
                    floors. Requires surveyor verification.
                  </p>
                </>
              )}
            </div>
            {selP && selP.property_type === "building" && (
              <div className="mt-3 flex flex-col gap-2">
                <button className="btn-primary !py-1 text-xs" onClick={() => viewFull3d(selP)}>
                  View full 3D block
                </button>
                <button className="btn-teal !py-1 text-xs" onClick={() => setExplode((x) => !x)}>
                  {explode ? "Collapse floors" : "Explode floors"}
                </button>
                <button className="btn-ghost w-full !py-1 text-xs" onClick={() => nav("/surveyor")}>
                  Open designer (floors · rooms · owners)
                </button>
              </div>
            )}
            {(selP?.property_type === "underground_asset" || selP?.property_type === "basement") && (
              <button className="btn-ghost mt-2 !py-1 text-xs" onClick={() => { setUndergroundRaised(true); setLayers((s) => ({ ...s, underground: true })); }}>
                View underground
              </button>
            )}
            {selP && (
              <button className="btn-ghost mt-2 w-full !py-1 text-xs" onClick={() => nav(`/property/${selP.id}`)}>
                Open full report
              </button>
            )}
          </div>
        )}

        {/* Context menu (right click -> ML block mapping) */}
        {ctx && (
          <div className="absolute left-1/2 top-1/2 z-20 w-64 -translate-x-1/2 -translate-y-1/2 rounded border border-slate-200 bg-white p-3 shadow-xl">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-slate-700">Place a building block</p>
              <button className="text-slate-400 hover:text-slate-600" onClick={() => setCtx(null)}>
                ✕
              </button>
            </div>
            <p className="mt-1 text-[11px] text-slate-400">
              {ctx.lat.toFixed(6)}, {ctx.lon.toFixed(6)}
            </p>
            <button
              className="btn-teal mt-2 w-full justify-center !py-1.5 text-xs"
              disabled={placing}
              onClick={() => autoPlaceAt(ctx.lon, ctx.lat)}
            >
              {placing ? "Mapping with ML…" : "🧠 Map Block with ML"}
            </button>
            <p className="mt-1 text-[10px] leading-snug text-slate-400">
              Detects the parcel, edge-fits the block with ML and stacks floors.
            </p>
          </div>
        )}

        {/* Conflicts drawer */}
        {layers.conflicts && conflicts.length > 0 && (
          <div className="absolute bottom-24 left-3 z-10 w-80 rounded border border-rose-200 bg-white/95 p-3 shadow">
            <p className="text-xs font-semibold text-rose-700">
              ⚠ {conflicts.length} topology issue(s)
            </p>
            <div className="mt-1 max-h-40 overflow-y-auto text-xs text-slate-600">
              {conflicts.slice(0, 6).map((c) => (
                <p key={c.code + c.object_ids.join()}>
                  <span className="font-medium text-rose-600">{c.state}:</span> {c.message}
                </p>
              ))}
            </div>
          </div>
        )}

        {/* Notice toast */}
        {notice && (
          <div className="absolute bottom-24 right-3 z-10 max-w-sm rounded border border-slate-300 bg-white/95 px-3 py-2 text-xs text-slate-700 shadow">
            {notice}
          </div>
        )}

        {/* Bottom primary actions */}
        <div className="absolute bottom-3 left-1/2 z-10 flex -translate-x-1/2 gap-2 rounded-full border border-slate-200 bg-white/95 p-1.5 shadow">
          <button className="btn-primary" onClick={() => nav("/import")}>
            Import Data
          </button>
          <button className="btn-teal" onClick={runAnalysis}>
            AI Analyse
          </button>
        </div>

        {/* Analysis modal */}
        {analysis && (
          <div className="absolute inset-0 z-20 grid place-items-center bg-slate-900/40 p-4" onClick={() => setAnalysis(null)}>
            <div
              className="w-full max-w-xl rounded-lg bg-white p-5 shadow-xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-slate-800">AI Analysis results</h3>
                <button className="text-slate-400" onClick={() => setAnalysis(null)}>✕</button>
              </div>
              <div className="grid grid-cols-4 gap-2 text-center">
                {[
                  ["Objects", analysis.summary.objects_analysed],
                  ["Buildings", analysis.summary.buildings],
                  ["AI candidates", analysis.summary.ai_candidates],
                  ["Anomalies", analysis.summary.anomalies],
                ].map(([l, v]) => (
                  <div key={String(l)} className="rounded bg-slate-50 p-2">
                    <div className="text-lg font-semibold text-ulpin-navy">{v}</div>
                    <div className="text-[10px] uppercase text-slate-500">{l}</div>
                  </div>
                ))}
              </div>
              {analysis.ai_candidates.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs font-semibold text-purple-700">AI-derived candidates</p>
                  {analysis.ai_candidates.map((c) => (
                    <div key={c.ref_key} className="mt-1 flex items-center justify-between rounded border border-purple-200 bg-purple-50 px-2 py-1 text-xs">
                      <span>{c.name}</span>
                      <span>
                        {c.confidence != null ? `${Math.round(c.confidence * 100)}%` : "?"} ·{" "}
                        {c.needs_verification ? "needs verification" : "verified"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {analysis.anomalies.length > 0 && (
                <ul className="mt-3 list-disc pl-5 text-xs text-amber-700">
                  {analysis.anomalies.slice(0, 5).map((a, i) => (
                    <li key={i}>{a.message}</li>
                  ))}
                </ul>
              )}
              <p className="mt-3 text-[11px] text-slate-400">{analysis.disclaimer}</p>
              <div className="mt-3 flex justify-end">
                <button className="btn-ghost" onClick={() => setAnalysis(null)}>Close</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
