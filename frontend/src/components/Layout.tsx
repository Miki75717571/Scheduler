import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useAuth } from "../lib/auth-context";
import { HealthBadge } from "./HealthBadge";

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-background">
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="font-semibold">{t("common.appName")}</span>
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
