import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { apiClient } from "../api/client";

export function HealthBadge() {
  const { t } = useTranslation();
  const { isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiClient.get<{ status: string }>("/health"),
    retry: false,
  });

  const label = isLoading ? t("health.checking") : isError ? t("health.error") : t("health.ok");
  const colorClass = isLoading
    ? "bg-muted text-muted-foreground"
    : isError
      ? "bg-destructive text-destructive-foreground"
      : "bg-secondary text-secondary-foreground";

  return <span className={`rounded-full px-3 py-1 text-xs ${colorClass}`}>{label}</span>;
}
