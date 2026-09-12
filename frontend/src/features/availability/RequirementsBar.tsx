import { useTranslation } from "react-i18next";

import type { RuleCheckResult, ShiftType } from "../../api/types";
import { translateRuleParams } from "../../lib/ruleMessages";
import { cn } from "../../lib/utils";

interface RequirementsBarProps {
  validation: RuleCheckResult[];
  shiftTypesByCode: Record<string, ShiftType>;
}

export function RequirementsBar({ validation, shiftTypesByCode }: RequirementsBarProps) {
  const { t, i18n } = useTranslation();

  if (validation.length === 0) return null;

  const allPassed = validation.every((r) => r.passed);

  return (
    <div className="sticky top-0 z-20 -mx-4 border-b border-border bg-background/95 px-4 py-2 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <p className="text-xs font-semibold text-muted-foreground">
        {t("availability.requirementsTitle")}
        {allPassed && (
          <span className="ml-2 text-emerald-700">{t("availability.requirementsAllMet")}</span>
        )}
      </p>
      <ul className="mt-1 flex flex-wrap gap-1.5">
        {validation.map((result) => {
          const params = translateRuleParams(result, shiftTypesByCode, t, i18n.language);
          const badgeClass = result.passed
            ? "bg-emerald-100 text-emerald-800"
            : result.severity === "HARD"
              ? "bg-rose-100 text-rose-800"
              : "bg-amber-100 text-amber-900";
          const icon = result.passed ? "✓" : result.severity === "HARD" ? "✗" : "!";
          return (
            <li
              key={result.rule_code}
              className={cn(
                "flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium",
                badgeClass,
              )}
            >
              <span aria-hidden>{icon}</span>
              <span>{t(result.message_key, params)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
