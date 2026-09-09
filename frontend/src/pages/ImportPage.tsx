import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import { api, uploadPreview } from "../lib/api";
import { useAuth } from "../lib/auth";

const SUPPORTED = [
  ["json", "JSON"],
  ["jsonl", "JSONL"],
  ["geojson", "GeoJSON"],
  ["cityjson", "CityJSON"],
  ["glb / gltf", "GLB / glTF (recognized, disabled in MVP)"],
];

interface PreviewRecord {
  kind: string;
  external_id: string;
  zmin: number | null;
  zmax: number | null;
  parcel_ref?: string | null;
  parent_ref?: string | null;
  warnings?: string[];
}

interface Preview {
  token: string;
  filename: string;
  format: string;
  crs: { epsg: number | null; note: string };
  record_count: number;
  warnings: string[];
  records: PreviewRecord[];
}

const STEPS = [
  "File detected",
  "Schema validated",
  "CRS resolved",
  "Geometry processed",
  "3D objects generated",
  "Topology checked",
];

export default function ImportPage() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [phase, setPhase] = useState(0); // cosmetic import-progress step
  const inputRef = useRef<HTMLInputElement>(null);

  if (user?.role === "viewer") {
    return (
      <Layout>
        <div className="grid h-full place-items-center text-sm text-slate-500">
          Viewer accounts cannot import data. Sign in as surveyor/admin to upload.
        </div>
      </Layout>
    );
  }

  async function handleFile(file: File) {
    setError("");
    setPreview(null);
    setBusy(true);
    setPhase(1);
    try {
      const res = await uploadPreview(file);
      setPhase(2);
      setPreview(res as Preview);
      // cosmetic progress after parse
      let p = 2;
      const timer = setInterval(() => {
        p += 1;
        setPhase(p);
        if (p >= STEPS.length) clearInterval(timer);
      }, 180);
    } catch (err) {
      setPhase(0);
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setBusy(false);
    }
  }

  async function commit() {
    if (!preview) return;
    setBusy(true);
    setError("");
    try {
      const res = await api<any>(`/uploads/${preview.token}/commit`, { method: "POST" });
      nav("/map");
      alert(
        `Imported: ${res.counts.buildings} building(s), ${res.counts.floors} floor(s), ` +
          `${res.counts.units} unit(s). Validation: ${res.validation.state}.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Commit failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Layout>
      <div className="mx-auto max-w-3xl p-6">
        <h1 className="text-lg font-semibold text-slate-800">Import Data</h1>
        <p className="text-sm text-slate-500">
          Upload a supported file. It is detected, validated, geometry is
          processed and topology checked before anything is committed.
        </p>

        <div
          className={`mt-4 rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
            drag ? "border-ulpin-teal bg-emerald-50" : "border-slate-300 bg-white"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            const f = e.dataTransfer.files?.[0];
            if (f) handleFile(f);
          }}
        >
          <p className="text-sm text-slate-600">Drag &amp; drop a file here, or</p>
          <button className="btn-primary mt-2" onClick={() => inputRef.current?.click()}>
            Choose file
          </button>
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept=".json,.jsonl,.geojson,.cityjson,.glb,.gltf"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
              e.currentTarget.value = "";
            }}
          />
          <div className="mt-3 flex flex-wrap justify-center gap-1.5">
            {SUPPORTED.map(([ext, label]) => (
              <span
                key={ext}
                className="rounded bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500"
              >
                {label}
              </span>
            ))}
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        {busy && !preview && (
          <div className="mt-4 rounded border border-slate-200 bg-white p-4">
            <p className="text-sm font-medium text-slate-700">Processing…</p>
            <ul className="mt-2 space-y-1 text-sm">
              {STEPS.slice(0, phase).map((s) => (
                <li key={s} className="text-emerald-600">
                  ✓ {s}
                </li>
              ))}
            </ul>
          </div>
        )}

        {preview && (
          <div className="mt-4 rounded border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-sm font-semibold text-slate-800">{preview.filename}</h2>
                <p className="text-xs text-slate-500">
                  Format: <b>{preview.format}</b> · {preview.record_count} record(s) · CRS:{" "}
                  {preview.crs.epsg ?? "unknown"} ({preview.crs.note})
                </p>
              </div>
              <span className="rounded bg-emerald-100 px-2 py-1 text-xs text-emerald-700">
                Preview — not committed
              </span>
            </div>
            <div className="mt-3 max-h-64 overflow-auto rounded border border-slate-100">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-2 py-1">Kind</th>
                    <th className="px-2 py-1">Id</th>
                    <th className="px-2 py-1">Parcel</th>
                    <th className="px-2 py-1">Parent</th>
                    <th className="px-2 py-1">Z range</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.records.map((r) => (
                    <tr key={r.kind + r.external_id} className="border-t border-slate-100">
                      <td className="px-2 py-1 text-slate-600">{r.kind}</td>
                      <td className="px-2 py-1">{r.external_id}</td>
                      <td className="px-2 py-1">{r.parcel_ref || "—"}</td>
                      <td className="px-2 py-1">{r.parent_ref || "—"}</td>
                      <td className="px-2 py-1">
                        {r.zmin != null ? `${r.zmin}–${r.zmax}` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {preview.warnings.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-xs text-amber-600">
                {preview.warnings.slice(0, 5).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
            <div className="mt-3 flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setPreview(null)}>
                Cancel
              </button>
              <button className="btn-teal" disabled={busy} onClick={commit}>
                Commit import
              </button>
            </div>
          </div>
        )}

        <div className="mt-6 rounded border border-slate-200 bg-white p-4 text-xs leading-relaxed text-slate-500">
          <b>Sample files</b> (in the repo under <code>backend/data/samples/</code>):
          <code> sample.parcels.geojson</code>, <code>sample.properties.json</code>,{" "}
          <code>sample.properties.jsonl</code>, <code>sample.city.json</code>. GLB/glTF and
          other formats are recognized but not enabled in this MVP.
        </div>
      </div>
    </Layout>
  );
}
