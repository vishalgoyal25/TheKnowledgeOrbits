/**
 * userstate.ts — Profile, preferences, progress, and userstate API calls.
 * All endpoints require JWT (apiClient injects it automatically).
 *
 * Endpoints map to engines/userstate/ backend:
 *   GET/PATCH /api/v1/userstate/profile/
 *   PATCH     /api/v1/userstate/profile/update/
 *   POST      /api/v1/userstate/profile/avatar/
 *   DELETE    /api/v1/userstate/profile/avatar/delete/
 *   GET       /api/v1/userstate/progress/
 *   GET/PATCH /api/v1/userstate/preferences/
 */

import apiClient from "./client";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface UserProfile {
  full_name: string;
  email: string;
  is_verified: boolean;
  subscription_tier: "free" | "premium" | "enterprise";
  created_at: string;
  avatar_url: string;
  bio: string;
}

export interface UserProgress {
  total_articles_read: number;
  total_quizzes_taken: number;
  current_streak: number;
  syllabus_coverage_percent: number;
  updated_at: string;
}

export interface UserPreferences {
  email_weekly_report: boolean;
  email_orbit_alerts: boolean;
  email_comment_replies: boolean;
  updated_at: string;
}

// ── Profile ───────────────────────────────────────────────────────────────────

export async function getProfile(): Promise<UserProfile> {
  const res = await apiClient.get("/userstate/profile/");
  return res.data;
}

export async function updateProfile(
  data: Partial<Pick<UserProfile, "full_name" | "bio">>,
): Promise<UserProfile> {
  const res = await apiClient.patch("/userstate/profile/update/", data);
  return res.data;
}

export async function uploadAvatar(
  file: File,
): Promise<{ avatar_url: string }> {
  const form = new FormData();
  form.append("avatar", file);
  const res = await apiClient.post("/userstate/profile/avatar/", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function deleteAvatar(): Promise<void> {
  await apiClient.delete("/userstate/profile/avatar/delete/");
}

// ── Progress ──────────────────────────────────────────────────────────────────

export async function getProgress(): Promise<UserProgress> {
  const res = await apiClient.get("/userstate/progress/");
  return res.data;
}

// ── Preferences ───────────────────────────────────────────────────────────────

export async function getPreferences(): Promise<UserPreferences> {
  const res = await apiClient.get("/userstate/preferences/");
  return res.data;
}

export async function updatePreferences(
  data: Partial<Omit<UserPreferences, "updated_at">>,
): Promise<UserPreferences> {
  const res = await apiClient.patch("/userstate/preferences/", data);
  return res.data;
}
