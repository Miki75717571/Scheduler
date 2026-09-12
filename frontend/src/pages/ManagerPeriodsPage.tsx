import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import type { SchedulePeriod } from "../api/types";
import { ApiErrorText } from "../components/ApiErrorText";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { createPeriod, fetchPeriods } from "../features/manager/api";

const createPeriodSchema = z.object({
  year: z.coerce.number().int().min(2000).max(2100),
  month: z.coerce.number().int().min(1).max(12),
  deadline: z.string().optional(),
});

type CreatePeriodForm = z.infer<typeof createPeriodSchema>;

function monthLabel(period: SchedulePeriod, language: string): string {
  return new Intl.DateTimeFormat(language === "pl" ? "pl-PL" : "en-US", {
    month: "long",
    year: "numeric",
  }).format(new Date(period.year, period.month - 1, 1));
}

export function ManagerPeriodsPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [createError, setCreateError] = useState<unknown>(null);

  const periodsQuery = useQuery({ queryKey: ["periods"], queryFn: fetchPeriods });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreatePeriodForm>({
    resolver: zodResolver(createPeriodSchema),
    defaultValues: { year: new Date().getFullYear(), month: new Date().getMonth() + 1 },
  });

  const onSubmit = async (values: CreatePeriodForm) => {
    setCreateError(null);
    try {
      const period = await createPeriod({
        year: values.year,
        month: values.month,
        availability_deadline: values.deadline ? new Date(values.deadline).toISOString() : null,
      });
      await queryClient.invalidateQueries({ queryKey: ["periods"] });
      reset();
      navigate(`/manager/periods/${period.id}`);
    } catch (error) {
      setCreateError(error);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{t("manager.periodsTitle")}</h1>

      <form onSubmit={(event) => void handleSubmit(onSubmit)(event)} className="space-y-3 rounded-md border border-border p-4">
        <h2 className="text-sm font-semibold">{t("manager.createPeriod")}</h2>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label htmlFor="year">{t("manager.year")}</Label>
            <Input id="year" type="number" {...register("year")} />
            {errors.year && <p className="text-sm text-destructive">{t("validation.required")}</p>}
          </div>
          <div className="space-y-1">
            <Label htmlFor="month">{t("manager.month")}</Label>
            <Input id="month" type="number" min={1} max={12} {...register("month")} />
            {errors.month && <p className="text-sm text-destructive">{t("validation.required")}</p>}
          </div>
        </div>
        <div className="space-y-1">
          <Label htmlFor="deadline">{t("manager.deadlineOptional")}</Label>
          <Input id="deadline" type="datetime-local" {...register("deadline")} />
        </div>
        {createError !== null && <ApiErrorText error={createError} />}
        <Button type="submit" disabled={isSubmitting}>
          {t("manager.createButton")}
        </Button>
      </form>

      {periodsQuery.isLoading && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}
      {periodsQuery.isError && <ApiErrorText error={periodsQuery.error} />}
      {periodsQuery.data && periodsQuery.data.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("availability.noPeriods")}</p>
      )}

      {periodsQuery.data && periodsQuery.data.length > 0 && (
        <ul className="divide-y divide-border rounded-md border border-border">
          {periodsQuery.data.map((period) => (
            <li key={period.id}>
              <Link
                to={`/manager/periods/${period.id}`}
                className="flex items-center justify-between px-4 py-3 text-sm hover:bg-secondary"
              >
                <span>{monthLabel(period, i18n.language)}</span>
                <span className="text-muted-foreground">{t(`manager.stateLabel.${period.state}`)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
