import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { apiClient } from "../api/client";
import type { User } from "../api/types";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { useAuth } from "../lib/auth-context";

interface ProfileForm {
  full_name: string;
  phone: string;
  locale: string;
  password: string;
}

export function ProfilePage() {
  const { t } = useTranslation();
  const { user, refreshUser } = useAuth();
  const [saved, setSaved] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<ProfileForm>({
    defaultValues: {
      full_name: user?.full_name ?? "",
      phone: user?.phone ?? "",
      locale: user?.locale ?? "pl",
      password: "",
    },
  });

  if (!user) {
    return null;
  }

  const onSubmit = async (values: ProfileForm) => {
    setSaved(false);
    await apiClient.patch<User>("/users/me", {
      full_name: values.full_name,
      phone: values.phone || null,
      locale: values.locale,
      password: values.password || undefined,
    });
    await refreshUser();
    setSaved(true);
  };

  return (
    <form onSubmit={(event) => void handleSubmit(onSubmit)(event)} className="space-y-4">
      <h1 className="text-xl font-semibold">{t("profile.title")}</h1>

      <div className="space-y-1">
        <Label htmlFor="full_name">{t("profile.fullName")}</Label>
        <Input id="full_name" {...register("full_name", { required: true })} />
      </div>

      <div className="space-y-1">
        <Label htmlFor="phone">{t("profile.phone")}</Label>
        <Input id="phone" {...register("phone")} />
      </div>

      <div className="space-y-1">
        <Label htmlFor="locale">{t("profile.locale")}</Label>
        <select
          id="locale"
          {...register("locale")}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        >
          <option value="pl">Polski</option>
          <option value="en">English</option>
        </select>
      </div>

      <div className="space-y-1">
        <Label htmlFor="password">{t("profile.newPassword")}</Label>
        <Input id="password" type="password" {...register("password")} />
      </div>

      {saved && <p className="text-sm text-muted-foreground">{t("profile.saved")}</p>}

      <Button type="submit" disabled={isSubmitting}>
        {t("common.save")}
      </Button>
    </form>
  );
}
