import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import { Badge, Field, fmt, sourceBadge } from "../components/ui";
import { api } from "../lib/api";

export default function PropertyPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const [prop, setProp] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!id) return;
    api<any>(`/properties/${encodeURIComponent(id)}`)
      .then(setProp)
      .catch((e) => setErr(e.message));
    api<any>(`/reports/property/${encodeURIComponent(id)}`)
      .then((r) => setReport(r.report))
      .catch(() => undefined);
  }, [id]);

  const badge = prop ? sourceBadge(prop) : null;

  return (
    <Layout>
      <div className="mx-auto max-w-3xl p-6">
        <button className="btn-ghost mb-3 !py-1 text-xs" onClick={() => nav(-1)}>
          ← Back
        </button>
        <h1 className="text-lg font-semibold text-slate-800">3D Property Report</h1>
        {err && <p className="mt-2 text-sm text-rose-600">{err}</p>}
        {!prop && !err && <p className="mt-3 text-sm text-slate-500">Loading…</p>}
        {prop && (
          <div className="mt-4 rounded border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-center gap-2">
              {badge && <Badge cls={badge.cls}>{badge.label}</Badge>}
              <Badge cls="bg-slate-100 text-slate-600 border-slate-300">{prop.property_type}</Badge>
            </div>
            <h2 className="mt-2 text-xl font-semibold text-ulpin-navy">{prop.name || prop.id}</h2>
            <p className="text-sm text-slate-500">{prop.id}</p>

            <div className="mt-4 rounded bg-slate-50 p-3">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                3D ULPIN
              </div>
              <code className="mt-1 block text-sm text-ulpin-blue">{prop.ulpin || "—"}</code>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-x-6">
              <div>
                <Field label="Parcel" value={prop.parcel_id} />
                <Field label="Parent" value={prop.parent_id} />
                <Field label="Status" value={prop.status} />
                <Field label="Version" value={`V${prop.version}`} />
                <Field label="Source" value={prop.source_type.replace(/_/g, " ")} />
                <Field label="Source file" value={prop.source_file || "—"} />
              </div>
              <div>
                <Field label="Z min" value={`${fmt(prop.zmin, 2)} m`} />
                <Field label="Z max" value={`${fmt(prop.zmax, 2)} m`} />
                <Field label="Height" value={prop.height_m != null ? `${fmt(prop.height_m, 2)} m` : "—"} />
                <Field label="Area" value={prop.area_m2 != null ? `${fmt(prop.area_m2, 1)} m²` : "—"} />
                <Field label="Volume" value={prop.volume_m3 != null ? `${fmt(prop.volume_m3, 1)} m³` : "—"} />
                <Field label="Updated" value={prop.updated_at ? new Date(prop.updated_at).toLocaleString() : "—"} />
              </div>
            </div>

            {prop.model_name && (
              <div className="mt-3 rounded border border-purple-200 bg-purple-50 p-3 text-xs text-purple-800">
                <b>AI-derived</b> — model {prop.model_name} (v{prop.model_version ?? "?"})
                {prop.confidence != null && ` · confidence ${Math.round(prop.confidence * 100)}%`}.{" "}
                Requires human verification before use as a cadastral boundary.
              </div>
            )}
            <div className="mt-3 rounded bg-amber-50 p-3 text-xs text-amber-700">
              {report?.notice || "Demonstration dataset — not an official land record."}
            </div>
            {report && (
              <p className="mt-3 text-[11px] text-slate-400">
                Report generated {new Date(report.generated_at).toLocaleString()} · fields:{" "}
                {report.fields.join(", ")}
              </p>
            )}
          </div>
        )}
      </div>
    </Layout>
  );
}
