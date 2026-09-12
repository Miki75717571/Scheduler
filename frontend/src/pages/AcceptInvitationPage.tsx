import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import { ApiError, apiClient } from "../api/client";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

const acceptSchema = z.object({
  full_name: z.string().min(1),
  password: z.string().min(8),
});

type AcceptForm = z.infer<typeof acceptSchema>;

interface InvitationPreview {
  email: string;
  role: string;
  expires_at: string;
}

export function AcceptInvitationPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [previewErrorKey, setPreviewErrorKey] = useState<string | null>(null);
  const [submitErrorKey, setSubmitErrorKey] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AcceptForm>({ resolver: zodResolver(acceptSchema) });

  useEffect(() => {
    if (!token) {
      setPreviewErrorKey("invitation.not_found");
      return;
    }
    apiClient
      .get<InvitationPreview>(`/invitations/${encodeURIComponent(token)}`)
      .then(setPreview)
      .catch((error: unknown) => {
        setPreviewErrorKey(error instanceof ApiError ? error.messageKey : "error.unknown");
      });
  }, [token]);

  const onSubmit = async (values: AcceptForm) => {
    setSubmitErrorKey(null);
    try {
      await apiClient.post("/invitations/accept", { token, ...values });
      setSuccess(true);
    } catch (error) {
      setSubmitErrorKey(error instanceof ApiError ? error.messageKey : "error.unknown");
    }
  };

  if (previewErrorKey) {
    return (
      <p className="text-sm text-destructive">
        {t(`apiErrors.${previewErrorKey}`, { defaultValue: t("error.unknown") })}
      </p>
    );
  }

  if (success) {
    return <p>{t("invitation.success")}</p>;
  }

  if (!preview) {
    return <p>{t("common.loading")}</p>;
  }

  return (
    <form onSubmit={(event) => void handleSubmit(onSubmit)(event)} className="space-y-4">
      <h1 className="text-xl font-semibold">{t("invitation.acceptTitle")}</h1>
      <p className="text-sm text-muted-foreground">{preview.email}</p>

      <div className="space-y-1">
        <Label htmlFor="full_name">{t("invitation.fullName")}</Label>
        <Input id="full_name" {...register("full_name")} />
        {errors.full_name && <p className="text-sm text-destructive">{t("validation.required")}</p>}
      </div>

      <div className="space-y-1">
        <Label htmlFor="password">{t("invitation.password")}</Label>
        <Input id="password" type="password" {...register("password")} />
        {errors.password && (
          <p className="text-sm text-destructive">{t("validation.minLength", { count: 8 })}</p>
        )}
      </div>

      {submitErrorKey && (
        <p className="text-sm text-destructive">
          {t(`apiErrors.${submitErrorKey}`, { defaultValue: t("error.unknown") })}
        </p>
      )}

      <Button type="submit" disabled={isSubmitting}>
        {t("invitation.acceptButton")}
      </Button>
    </form>
  );
}
