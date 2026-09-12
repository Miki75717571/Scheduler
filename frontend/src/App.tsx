import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { ManagerRoute } from "./components/ManagerRoute";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthProvider, useAuth } from "./lib/auth-context";
import { AcceptInvitationPage } from "./pages/AcceptInvitationPage";
import { AvailabilityPage } from "./pages/AvailabilityPage";
import { EmployeeSchedulePage } from "./pages/EmployeeSchedulePage";
import { LoginPage } from "./pages/LoginPage";
import { ManagerPeriodDetailPage } from "./pages/ManagerPeriodDetailPage";
import { ManagerPeriodsPage } from "./pages/ManagerPeriodsPage";
import { ManagerSchedulePage } from "./pages/ManagerSchedulePage";
import { ProfilePage } from "./pages/ProfilePage";

function AppRoutes() {
  const { user } = useAuth();
  const homePath = !user ? "/login" : user.role === "EMPLOYEE" ? "/availability" : "/manager/periods";

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/accept-invitation" element={<AcceptInvitationPage />} />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/availability"
        element={
          <ProtectedRoute>
            <AvailabilityPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/schedule"
        element={
          <ProtectedRoute>
            <EmployeeSchedulePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/manager/periods"
        element={
          <ManagerRoute>
            <ManagerPeriodsPage />
          </ManagerRoute>
        }
      />
      <Route
        path="/manager/periods/:periodId"
        element={
          <ManagerRoute>
            <ManagerPeriodDetailPage />
          </ManagerRoute>
        }
      />
      <Route
        path="/manager/periods/:periodId/schedule"
        element={
          <ManagerRoute>
            <ManagerSchedulePage />
          </ManagerRoute>
        }
      />
      <Route path="*" element={<Navigate to={homePath} replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Layout>
        <AppRoutes />
      </Layout>
    </AuthProvider>
  );
}
