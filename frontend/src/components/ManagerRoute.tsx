import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../lib/auth-context";

// Employees never reach the manager dashboard, in the nav (Layout.tsx hides
// the link), at the route (here), or at the API (require_role on every
// manager endpoint) - CLAUDE.md's "never rely on hiding UI elements".
export function ManagerRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (user.role === "EMPLOYEE") {
    return <Navigate to="/availability" replace />;
  }

  return <>{children}</>;
}
