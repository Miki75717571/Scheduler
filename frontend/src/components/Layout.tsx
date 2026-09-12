import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useAuth } from "../lib/auth-context";
import { HealthBadge } from "./HealthBadge";

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const isManager = user?.role === "MANAGER" || user?.role === "ADMIN";

  return (
    <div className="min-h-screen bg-background">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
        <span className="font-semibold">{t("common.appName")}</span>
        {user && (
          <nav className="flex items-center gap-4 text-sm text-muted-foreground">
            <Link to="/availability" className="hover:text-foreground">
              {t("nav.availability")}
            </Link>
            {isManager && (
              <Link to="/manager/periods" className="hover:text-foreground">
                {t("nav.manager")}
              </Link>
            )}
            <Link to="/profile" className="hover:text-foreground">
              {t("nav.profile")}
            </Link>
          </nav>
        )}
        <div className="flex items-center gap-3">
          <HealthBadge />
          {user && (
            <button
              type="button"
              onClick={() => void logout()}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              {t("auth.logout")}
            </button>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-2xl px-4 py-8">{children}</main>
    </div>
  );
}
