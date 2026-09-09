import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./lib/auth";
import AdminPage from "./pages/AdminPage";
import Community3DPage from "./pages/Community3DPage";
import ImportPage from "./pages/ImportPage";
import LoginPage from "./pages/LoginPage";
import MapPage from "./pages/MapPage";
import PropertyPage from "./pages/PropertyPage";
import SurveyorPage from "./pages/SurveyorPage";

function RequireAuth({ children }: { children: JSX.Element }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Navigate to="/map" replace />} />
      <Route
        path="/map"
        element={
          <RequireAuth>
            <MapPage />
          </RequireAuth>
        }
      />
      <Route
        path="/community-3d"
        element={
          <RequireAuth>
            <Community3DPage />
          </RequireAuth>
        }
      />
      <Route
        path="/import"
        element={
          <RequireAuth>
            <ImportPage />
          </RequireAuth>
        }
      />
      <Route
        path="/surveyor"
        element={
          <RequireAuth>
            <SurveyorPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin"
        element={
          <RequireAuth>
            <AdminPage />
          </RequireAuth>
        }
      />
      <Route
        path="/property/:id"
        element={
          <RequireAuth>
            <PropertyPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/map" replace />} />
    </Routes>
  );
}
