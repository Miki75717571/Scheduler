import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { ApiError } from "../api/client";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { useAuth } from "../lib/auth-context";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

type LoginForm = z.infer<typeof loginSchema>;

export function LoginPage() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [errorKey, setErrorKey] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (values: LoginForm) => {
    setErrorKey(null);
    try {
      await login(values.email, values.password);
      navigate("/profile");
    } catch (error) {
      setErrorKey(error instanceof ApiError ? error.messageKey : "error.unknown");
    }
  };

  return (
    <form onSubmit={(event) => void handleSubmit(onSubmit)(event)} className="space-y-4">
      <h1 className="text-xl font-semibold">{t("auth.loginTitle")}</h1>

      <div className="space-y-1">
        <Label htmlFor="email">{t("auth.email")}</Label>
        <Input id="email" type="email" {...register("email")} />
        {errors.email && <p className="text-sm text-destructive">{t("validation.required")}</p>}
      </div>

      <div className="space-y-1">
        <Label htmlFor="password">{t("auth.password")}</Label>
        <Input id="password" type="password" {...register("password")} />
        {errors.password && <p className="text-sm text-destructive">{t("validation.required")}</p>}
      </div>

      {errorKey && (
        <p className="text-sm text-destructive">
          {t(`apiErrors.${errorKey}`, { defaultValue: t("error.unknown") })}
        </p>
      )}

      <Button type="submit" disabled={isSubmitting}>
        {t("auth.loginButton")}
      </Button>
    </form>
  );
}
