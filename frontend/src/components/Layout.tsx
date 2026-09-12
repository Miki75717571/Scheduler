import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";

import { useAuth } from "../lib/auth-context";
import { cn } from "../lib/utils";
import { HealthBadge } from "./HealthBadge";

// The manager schedule calendar is the one desktop-first screen in the app
// (see the task brief: "the screen I will live in") - every other page stays
// narrow and centred like the mobile-first availability calendar, so only
// that route gets the wide container.
const WIDE_ROUTE = /^\/manager\/periods\/[^/]+\/schedule$/;

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const location = useLocation();
  const isManager = user?.role === "MANAGER" || user?.role === "ADMIN";
  const isAdmin = user?.role === "ADMIN";
  const wide = WIDE_ROUTE.test(location.pathname);

  return (
    <div className="min-h-screen bg-background">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3 print:hidden">
        <span className="font-semibold">{t("common.appName")}</span>
        {user && (
          <nav className="flex items-center gap-4 text-sm text-muted-foreground">
            <Link to="/availability" className="hover:text-foreground">
              {t("nav.availability")}
            </Link>
            <Link to="/schedule" className="hover:text-foreground">
              {t("nav.schedule")}
            </Link>
            {isManager && (
              <Link to="/manager/periods" className="hover:text-foreground">
                {t("nav.manager")}
              </Link>
            )}
            {isManager && (
              <Link to="/manager/scores" className="hover:text-foreground">
                {t("nav.scores")}
              </Link>
            )}
            {isAdmin && (
              <Link to="/admin/criteria" className="hover:text-foreground">
                {t("nav.criteria")}
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
      <main className={cn("mx-auto px-4 py-8 print:p-0", wide ? "max-w-[1600px]" : "max-w-2xl")}>
        {children}
      </main>
    </div>
  );
}
