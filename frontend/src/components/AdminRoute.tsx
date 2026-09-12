import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../lib/auth-context";

// Criteria management is admin-only (ARCHITECTURE.md ss5: "Manage users,
// rules, criteria, weights" - Admin, not Manager) - enforced here, and again
// at the API (require_role(Role.ADMIN) on every score-criteria mutation),
// per CLAUDE.md's "never rely on hiding UI elements".
export function AdminRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (user.role !== "ADMIN") {
    return <Navigate to="/manager/periods" replace />;
  }

  return <>{children}</>;
}
