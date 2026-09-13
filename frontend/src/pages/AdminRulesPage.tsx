import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { Rule } from "../api/types";
import { ApiErrorText } from "../components/ApiErrorText";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { fetchRestConflicts, fetchRules, updateRuleParams } from "../features/rules/api";

function RuleRow({
  rule,
  onSave,
}: {
  rule: Rule;
  onSave: (id: string, params: Record<string, unknown>) => Promise<void>;
}) {
  const { t, i18n } = useTranslation();
  const [draft, setDraft] = useState<Record<string, unknown>>(rule.params);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    setDraft(rule.params);
  }, [rule.params]);

  const dirty = JSON.stringify(draft) !== JSON.stringify(rule.params);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await onSave(rule.id, draft);
      setSaved(true);
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <tr className="border-b border-border/60 align-top">
      <td className="py-1.5 pr-2 font-medium">
        {i18n.language === "pl" ? rule.name_pl : rule.name_en}
        <div className="text-[11px] uppercase text-muted-foreground">{rule.type}</div>
      </td>
      <td className="py-1.5 pr-2 text-xs">{t(`adminRules.phase.${rule.phase}`)}</td>
      <td className="py-1.5 pr-2 text-xs">{t(`adminRules.severity.${rule.severity}`)}</td>
      <td className="py-1.5 pr-2">
        <div className="flex flex-wrap gap-2">
          {Object.entries(draft).map(([key, value]) => (
            <div key={key} className="space-y-0.5">
              <label className="block text-[11px] text-muted-foreground">{key}</label>
              <Input
                className="h-8 w-24"
                value={String(value)}
                onChange={(e) => {
                  const raw = e.target.value;
                  const numeric = Number(raw);
                  setDraft((prev) => ({
                    ...prev,
                    [key]: typeof value === "number" && !Number.isNaN(numeric) ? numeric : raw,
                  }));
                }}
              />
            </div>
          ))}
        </div>
      </td>
      <td className="py-1.5 pr-2">
        <Button
          type="button"
          size="sm"
          disabled={!dirty || saving}
          onClick={() => void handleSave()}
        >
          {t("common.save")}
        </Button>
        {saved && !dirty && (
          <span className="ml-2 text-xs text-emerald-700">{t("adminRules.saved")}</span>
        )}
        {error !== null && <ApiErrorText className="mt-1 text-xs text-destructive" error={error} />}
      </td>
    </tr>
  );
}

export function AdminRulesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const rulesQuery = useQuery({ queryKey: ["rules"], queryFn: fetchRules });
  const conflictsQuery = useQuery({
    queryKey: ["rest-conflicts"],
    queryFn: fetchRestConflicts,
  });

  async function handleSave(id: string, params: Record<string, unknown>) {
    await updateRuleParams(id, params);
    await queryClient.invalidateQueries({ queryKey: ["rules"] });
    await queryClient.invalidateQueries({ queryKey: ["rest-conflicts"] });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{t("adminRules.title")}</h1>
      <p className="text-sm text-muted-foreground">{t("adminRules.intro")}</p>

      {conflictsQuery.data && conflictsQuery.data.length > 0 && (
        <div className="space-y-2 rounded-md border border-amber-400 bg-amber-50 p-3">
          <h2 className="text-sm font-semibold text-amber-900">
            {t("adminRules.restConflictBannerTitle")}
          </h2>
          <ul className="space-y-1 text-sm text-amber-900">
            {conflictsQuery.data.map((c) => (
              <li
                key={`${c.from_weekday}-${c.from_shift_type_code}-${c.to_weekday}-${c.to_shift_type_code}`}
              >
                {t("solver.rest_conflict", {
                  from_weekday: c.from_weekday,
                  from_shift_type_code: c.from_shift_type_code,
                  to_weekday: c.to_weekday,
                  to_shift_type_code: c.to_shift_type_code,
                  gap_hours: c.gap_hours,
                  required_hours: c.required_hours,
                })}
              </li>
            ))}
          </ul>
        </div>
      )}

      {rulesQuery.isLoading && (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      )}
      {rulesQuery.isError && <ApiErrorText error={rulesQuery.error} />}

      {rulesQuery.data && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-1 pr-2">{t("adminRules.columnRule")}</th>
                <th className="py-1 pr-2">{t("adminRules.columnPhase")}</th>
                <th className="py-1 pr-2">{t("adminRules.columnSeverity")}</th>
                <th className="py-1 pr-2">{t("adminRules.columnParams")}</th>
                <th className="py-1 pr-2">{t("adminRules.columnActions")}</th>
              </tr>
            </thead>
            <tbody>
              {rulesQuery.data.map((rule) => (
                <RuleRow key={rule.id} rule={rule} onSave={handleSave} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
