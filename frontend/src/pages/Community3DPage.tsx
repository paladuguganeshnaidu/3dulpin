import { Link } from "react-router-dom";
import Layout from "../components/Layout";

/**
 * Full-screen static CityJSON viewer adapted from the public 3dview project.
 * The heavy city tile stays outside the React bundle and is fetched by the
 * original Three.js viewer at runtime.
 */
export default function Community3DPage() {
  return (
    <Layout>
      <div className="relative h-full bg-[#0b1020]">
        <div className="pointer-events-none absolute left-4 top-3 z-10 rounded border border-slate-500/40 bg-slate-950/75 px-3 py-2 text-white shadow-lg">
          <p className="text-sm font-semibold">Nagarjuna community 3D demo</p>
          <p className="text-[11px] text-slate-300">
            Real CityJSON building tile · floor and unit assignment viewer
          </p>
        </div>
        <Link
          to="/map"
          className="absolute right-4 top-3 z-10 rounded border border-slate-400/50 bg-slate-950/80 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800"
        >
          Back to GIS map
        </Link>
        <iframe
          title="Full 3D community CityJSON viewer"
          src="/community-demo/3dmap.html"
          className="h-full w-full border-0"
        />
      </div>
    </Layout>
  );
}
