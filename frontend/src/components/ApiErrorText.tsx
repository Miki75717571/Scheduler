import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";

interface ApiErrorTextProps {
  error: unknown;
  className?: string;
}

// A raw TanStack Query `error` (or a caught mutation error) is only ever
// distinguishable by its ApiError.messageKey - never collapse it to the
// generic error.unknown fallback, so "server unreachable" reads differently
// from "wrong password" from "session expired" from "validation failed".
export function ApiErrorText({ error, className = "text-sm text-destructive" }: ApiErrorTextProps) {
  const { t } = useTranslation();
  const key = error instanceof ApiError ? error.messageKey : "error.unknown";
  return <p className={className}>{t(`apiErrors.${key}`, { defaultValue: t("error.unknown") })}</p>;
}
