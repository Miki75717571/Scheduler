import { apiClient } from "../../api/client";
import type { Invitation, Role } from "../../api/types";

export function fetchInvitations(): Promise<Invitation[]> {
  return apiClient.get<Invitation[]>("/invitations");
}

export function createInvitation(email: string, role: Role): Promise<Invitation> {
  return apiClient.post<Invitation>("/invitations", { email, role });
}

export function resendInvitation(id: string): Promise<Invitation> {
  return apiClient.post<Invitation>(`/invitations/${id}/resend`);
}

export function revokeInvitation(id: string): Promise<Invitation> {
  return apiClient.post<Invitation>(`/invitations/${id}/revoke`);
}
