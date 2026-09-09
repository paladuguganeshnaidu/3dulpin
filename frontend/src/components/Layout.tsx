import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

const roleLinks: Record<string, { to: string; label: string }[]> = {
  admin: [
    { to: "/community-3d", label: "3D Community" },
    { to: "/import", label: "Import" },
    { to: "/surveyor", label: "My Submissions" },
    { to: "/admin", label: "Admin" },
  ],
  surveyor: [
    { to: "/community-3d", label: "3D Community" },
    { to: "/import", label: "Import" },
    { to: "/surveyor", label: "My Submissions" },
  ],
  viewer: [{ to: "/community-3d", label: "3D Community" }],
};

export default function Layout({
  children,
  onSearch,
}: {
  children: React.ReactNode;
  onSearch?: (q: string) => void;
}) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const role = user?.role || "viewer";
  const links = [{ to: "/map", label: "Map" }, ...(roleLinks[role] || [])];

  return (
    <div className="flex h-full flex-col">
      <header className="z-20 flex h-12 items-center gap-3 border-b border-slate-200 bg-white px-4 shadow-sm">
        <Link to="/map" className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded bg-ulpin-navy text-[13px] font-bold text-emerald-400">
            3D
          </span>
          <span className="text-sm font-semibold tracking-tight text-slate-800">
            India 3D ULPIN
          </span>
        </Link>
        <nav className="ml-3 flex items-center gap-1">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              className={({ isActive }) =>
                `rounded px-2.5 py-1 text-sm ${
                  isActive ? "bg-ulpin-navy text-white" : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          {onSearch && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const fd = new FormData(e.currentTarget);
                const q = String(fd.get("q") || "");
                if (q.trim()) onSearch(q.trim());
              }}
            >
              <input
                name="q"
                placeholder="Search parcel / 3D ULPIN…"
                className="w-64 rounded border border-slate-300 px-2.5 py-1 text-sm outline-none focus:border-ulpin-blue"
              />
            </form>
          )}
          {user ? (
            <div className="flex items-center gap-2">
              <span className="rounded bg-slate-100 px-2 py-0.5 text-xs capitalize text-slate-600">
                {user.role}
              </span>
              <span className="text-sm text-slate-700">{user.username}</span>
              <button
                className="btn-ghost !py-1 text-xs"
                onClick={() => {
                  logout();
                  navigate("/login");
                }}
              >
                Sign out
              </button>
            </div>
          ) : (
            <Link to="/login" className="btn-primary">
              Sign in
            </Link>
          )}
        </div>
      </header>
      <main className="min-h-0 flex-1">{children}</main>
    </div>
  );
}
