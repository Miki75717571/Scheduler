import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { Role } from "../api/types";
import { ApiErrorText } from "../components/ApiErrorText";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  createInvitation,
  fetchInvitations,
  resendInvitation,
  revokeInvitation,
} from "../features/invitations/api";

const STATUS_STYLE: Record<string, string> = {
  PENDING: "text-amber-700",
  ACCEPTED: "text-emerald-700",
  EXPIRED: "text-muted-foreground",
  REVOKED: "text-destructive",
};

export function AdminInvitationsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("EMPLOYEE");
  const [createError, setCreateError] = useState<unknown>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const invitationsQuery = useQuery({ queryKey: ["invitations"], queryFn: fetchInvitations });

  async function handleInvite() {
    setCreateError(null);
    try {
      await createInvitation(email, role);
      setEmail("");
      await queryClient.invalidateQueries({ queryKey: ["invitations"] });
    } catch (error) {
      setCreateError(error);
    }
  }

  async function handleResend(id: string) {
    setPendingId(id);
    try {
      await resendInvitation(id);
      await queryClient.invalidateQueries({ queryKey: ["invitations"] });
    } finally {
      setPendingId(null);
    }
  }

  async function handleRevoke(id: string) {
    setPendingId(id);
    try {
      await revokeInvitation(id);
      await queryClient.invalidateQueries({ queryKey: ["invitations"] });
    } finally {
      setPendingId(null);
    }
  }

  async function handleCopy(id: string, url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedId(id);
      setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 2000);
    } catch {
      // Clipboard API unavailable (e.g. insecure context) - the link is
      // still shown as plain text, so the admin can select-and-copy by hand.
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{t("invitations.title")}</h1>
      <p className="text-sm text-muted-foreground">{t("invitations.intro")}</p>

      <section className="space-y-2 rounded-lg border border-border p-3">
        <h2 className="text-sm font-semibold">{t("invitations.inviteTitle")}</h2>
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <Label htmlFor="invite-email">{t("invitations.email")}</Label>
            <Input
              id="invite-email"
              type="email"
              className="h-9 w-56"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="invite-role">{t("invitations.role")}</Label>
            <select
              id="invite-role"
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
              className="h-9 w-40 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="EMPLOYEE">{t("invitations.roleEmployee")}</option>
              <option value="MANAGER">{t("invitations.roleManager")}</option>
              <option value="ADMIN">{t("invitations.roleAdmin")}</option>
            </select>
          </div>
          <Button type="button" disabled={!email} onClick={() => void handleInvite()}>
            {t("invitations.inviteButton")}
          </Button>
        </div>
        {createError !== null && <ApiErrorText error={createError} />}
      </section>

      {invitationsQuery.isLoading && (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      )}
      {invitationsQuery.isError && <ApiErrorText error={invitationsQuery.error} />}

      {invitationsQuery.data && invitationsQuery.data.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("invitations.empty")}</p>
      )}

      {invitationsQuery.data && invitationsQuery.data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-1 pr-2">{t("invitations.columnEmail")}</th>
                <th className="py-1 pr-2">{t("invitations.columnRole")}</th>
                <th className="py-1 pr-2">{t("invitations.columnStatus")}</th>
                <th className="py-1 pr-2">{t("invitations.columnExpires")}</th>
                <th className="py-1 pr-2">{t("invitations.columnLink")}</th>
                <th className="py-1 pr-2">{t("invitations.columnActions")}</th>
              </tr>
            </thead>
            <tbody>
              {invitationsQuery.data.map((invitation) => (
                <tr key={invitation.id} className="border-b border-border/60 align-top">
                  <td className="py-1.5 pr-2">{invitation.email}</td>
                  <td className="py-1.5 pr-2">{invitation.role}</td>
                  <td className={`py-1.5 pr-2 font-medium ${STATUS_STYLE[invitation.status]}`}>
                    {t(`invitations.status.${invitation.status}`)}
                  </td>
                  <td className="py-1.5 pr-2 text-muted-foreground">
                    {new Date(invitation.expires_at).toLocaleString(
                      i18n.language === "pl" ? "pl-PL" : "en-US",
                      { dateStyle: "medium", timeStyle: "short" },
                    )}
                  </td>
                  <td className="max-w-[220px] py-1.5 pr-2">
                    {invitation.accept_url && invitation.status === "PENDING" ? (
                      <div className="flex items-center gap-1">
                        <span
                          className="truncate text-xs text-muted-foreground"
                          title={invitation.accept_url}
                        >
                          {invitation.accept_url}
                        </span>
                        <button
                          type="button"
                          className="shrink-0 rounded border border-input px-1.5 py-0.5 text-xs hover:bg-secondary"
                          onClick={() =>
                            void handleCopy(invitation.id, invitation.accept_url as string)
                          }
                        >
                          {copiedId === invitation.id
                            ? t("invitations.copied")
                            : t("invitations.copyLink")}
                        </button>
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="py-1.5 pr-2">
                    {invitation.status === "PENDING" || invitation.status === "EXPIRED" ? (
                      <div className="flex gap-2">
                        <button
                          type="button"
                          disabled={pendingId === invitation.id}
                          className="text-xs text-primary underline-offset-2 hover:underline disabled:opacity-50"
                          onClick={() => void handleResend(invitation.id)}
                        >
                          {t("invitations.resendButton")}
                        </button>
                        {invitation.status === "PENDING" && (
                          <button
                            type="button"
                            disabled={pendingId === invitation.id}
                            className="text-xs text-destructive underline-offset-2 hover:underline disabled:opacity-50"
                            onClick={() => void handleRevoke(invitation.id)}
                          >
                            {t("invitations.revokeButton")}
                          </button>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
