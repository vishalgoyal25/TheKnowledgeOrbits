"use client";

/**
 * Profile Page — fully wired (Phase F, FEATURES7)
 *
 * Real data from:
 *   GET /api/v1/userstate/profile/   → name, email, avatar, tier, created_at, bio
 *   GET /api/v1/userstate/progress/  → articles, quizzes, streak
 *
 * Features:
 *   - Inline name edit (pencil icon → input → save)
 *   - Avatar upload (camera overlay) + remove
 *   - Real stats + member-since date
 *   - Subscription tier badge with colours
 *   - Loading skeletons + error states
 */

import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { useToast } from "@/hooks/use-toast";
import {
  deleteAvatar,
  getProfile,
  getProgress,
  updateProfile,
  uploadAvatar,
  type UserProfile,
  type UserProgress,
} from "@/lib/api/userstate";
import {
  BadgeCheck,
  Calendar,
  Camera,
  CheckCircle2,
  Flame,
  Loader2,
  Mail,
  Pencil,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatMemberSince(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString("en-IN", {
      month: "long",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

const TIER_STYLES: Record<string, string> = {
  free: "bg-gray-100 text-gray-600 border-gray-200",
  premium: "bg-blue-100 text-blue-700 border-blue-200",
  enterprise: "bg-indigo-100 text-indigo-700 border-indigo-200",
};

// ── Skeleton ──────────────────────────────────────────────────────────────────

function ProfileSkeleton() {
  return (
    <div className="max-w-4xl mx-auto p-6 lg:p-12 animate-pulse">
      <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="h-32 bg-gray-200" />
        <div className="px-8 pb-8">
          <div className="relative -mt-12 mb-6">
            <div className="h-24 w-24 rounded-2xl bg-gray-200" />
          </div>
          <div className="h-8 w-48 bg-gray-200 rounded mb-2" />
          <div className="h-4 w-64 bg-gray-100 rounded mb-8" />
          <div className="grid grid-cols-2 gap-4 mt-8">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-20 bg-gray-100 rounded-2xl" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ProfilePage() {
  const { toast } = useToast();

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [progress, setProgress] = useState<UserProgress | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [progressLoading, setProgressLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Inline name edit
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [nameSaving, setNameSaving] = useState(false);

  // Avatar
  const [avatarUploading, setAvatarUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Fetch on mount ──────────────────────────────────────────────────────────
  useEffect(() => {
    getProfile()
      .then((p) => {
        setProfile(p);
        setNameValue(p.full_name);
      })
      .catch(() => setError("Could not load profile."))
      .finally(() => setProfileLoading(false));

    getProgress()
      .then(setProgress)
      .catch(() => {
        /* progress is non-critical */
      })
      .finally(() => setProgressLoading(false));
  }, []);

  // ── Inline name save ────────────────────────────────────────────────────────
  const handleNameSave = async () => {
    if (!profile || nameValue.trim() === profile.full_name) {
      setEditingName(false);
      return;
    }
    setNameSaving(true);
    try {
      const updated = await updateProfile({ full_name: nameValue.trim() });
      setProfile(updated);
      toast({ title: "Name updated ✓" });
      setEditingName(false);
    } catch {
      toast({
        title: "Failed to update name",
        variant: "destructive",
      });
    } finally {
      setNameSaving(false);
    }
  };

  // ── Avatar upload ───────────────────────────────────────────────────────────
  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAvatarUploading(true);
    try {
      const { avatar_url } = await uploadAvatar(file);
      setProfile((p) => (p ? { ...p, avatar_url } : p));
      toast({ title: "Avatar updated ✓" });
    } catch {
      toast({ title: "Upload failed", variant: "destructive" });
    } finally {
      setAvatarUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // ── Avatar remove ───────────────────────────────────────────────────────────
  const handleAvatarRemove = async () => {
    setAvatarUploading(true);
    try {
      await deleteAvatar();
      setProfile((p) => (p ? { ...p, avatar_url: "" } : p));
      toast({ title: "Avatar removed ✓" });
    } catch {
      toast({ title: "Remove failed", variant: "destructive" });
    } finally {
      setAvatarUploading(false);
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  if (profileLoading)
    return (
      <ProtectedRoute>
        <ProfileSkeleton />
      </ProtectedRoute>
    );

  if (error) {
    return (
      <ProtectedRoute>
        <div className="max-w-4xl mx-auto p-12 text-center text-red-500">
          {error}
        </div>
      </ProtectedRoute>
    );
  }

  const tierStyle =
    TIER_STYLES[profile?.subscription_tier ?? "free"] ?? TIER_STYLES.free;
  const initials = (
    profile?.full_name?.charAt(0) ||
    profile?.email?.charAt(0) ||
    "U"
  ).toUpperCase();

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto p-6 lg:p-12">
        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
          {/* Cover */}
          <div className="h-32 bg-gradient-to-r from-blue-600 to-indigo-700" />

          <div className="px-8 pb-8">
            {/* Avatar */}
            <div className="relative -mt-12 mb-6 flex items-end gap-3">
              <div className="relative h-24 w-24 flex-shrink-0">
                <div className="h-24 w-24 rounded-2xl bg-white p-1 shadow-lg">
                  {profile?.avatar_url ? (
                    <Image
                      src={profile.avatar_url}
                      alt={profile.full_name || "Avatar"}
                      fill
                      className="rounded-xl object-cover"
                      sizes="96px"
                    />
                  ) : (
                    <div className="h-full w-full rounded-xl bg-blue-100 flex items-center justify-center text-3xl font-black text-blue-600">
                      {initials}
                    </div>
                  )}
                </div>

                {/* Camera overlay */}
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={avatarUploading}
                  className="absolute inset-0 rounded-2xl flex items-center justify-center bg-black/40 opacity-0 hover:opacity-100 transition-opacity"
                  title="Change avatar"
                >
                  {avatarUploading ? (
                    <Loader2 className="h-5 w-5 text-white animate-spin" />
                  ) : (
                    <Camera className="h-5 w-5 text-white" />
                  )}
                </button>

                {/* Online dot */}
                <div className="absolute bottom-0 left-20 bg-green-500 border-4 border-white h-6 w-6 rounded-full shadow-sm" />
              </div>

              {/* Remove avatar button */}
              {profile?.avatar_url && (
                <button
                  onClick={handleAvatarRemove}
                  disabled={avatarUploading}
                  className="mb-1 flex items-center gap-1.5 text-xs text-red-500 hover:text-red-700 transition-colors disabled:opacity-50"
                  title="Remove avatar"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Remove
                </button>
              )}
            </div>

            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={handleAvatarChange}
            />

            {/* Name + tier */}
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
              <div>
                {/* Inline name edit */}
                {editingName ? (
                  <div className="flex items-center gap-2 mb-1">
                    <input
                      autoFocus
                      value={nameValue}
                      onChange={(e) => setNameValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleNameSave();
                        if (e.key === "Escape") {
                          setEditingName(false);
                          setNameValue(profile?.full_name ?? "");
                        }
                      }}
                      className="text-2xl font-bold text-gray-900 border-b-2 border-blue-500 bg-transparent outline-none w-64"
                    />
                    <button
                      onClick={handleNameSave}
                      disabled={nameSaving}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      {nameSaving ? (
                        <Loader2 className="h-5 w-5 animate-spin" />
                      ) : (
                        <CheckCircle2 className="h-5 w-5" />
                      )}
                    </button>
                    <button
                      onClick={() => {
                        setEditingName(false);
                        setNameValue(profile?.full_name ?? "");
                      }}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 mb-1">
                    <h1 className="text-3xl font-bold text-gray-900">
                      {profile?.full_name || "Aspirant"}
                    </h1>
                    <button
                      onClick={() => setEditingName(true)}
                      className="text-gray-400 hover:text-blue-500 transition-colors"
                      title="Edit name"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                  </div>
                )}

                <p className="text-gray-500 font-medium flex items-center gap-2 mt-1">
                  <Mail className="h-4 w-4" />
                  {profile?.email}
                </p>
              </div>

              <div
                className={`flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-sm border ${tierStyle}`}
              >
                <BadgeCheck className="h-4 w-4" />
                {(profile?.subscription_tier ?? "free")
                  .charAt(0)
                  .toUpperCase() +
                  (profile?.subscription_tier ?? "free").slice(1)}
              </div>
            </div>

            {/* Stats + Account Info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-12">
              {/* Account info */}
              <div className="space-y-6">
                <h3 className="text-lg font-bold text-gray-800 border-b pb-2">
                  Account Information
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-gray-50 rounded-lg">
                      <Calendar className="h-5 w-5 text-gray-400" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-gray-400 uppercase">
                        Member Since
                      </p>
                      <p className="text-sm font-semibold text-gray-700">
                        {profile?.created_at
                          ? formatMemberSince(profile.created_at)
                          : "—"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-gray-50 rounded-lg">
                      <ShieldCheck className="h-5 w-5 text-gray-400" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-gray-400 uppercase">
                        Account Status
                      </p>
                      {profile?.is_verified ? (
                        <p className="text-sm font-semibold text-green-600">
                          Verified & Active
                        </p>
                      ) : (
                        <p className="text-sm font-semibold text-amber-500">
                          Email not verified
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Learning stats */}
              <div className="space-y-6">
                <h3 className="text-lg font-bold text-gray-800 border-b pb-2">
                  Learning Stats
                </h3>
                {progressLoading ? (
                  <div className="grid grid-cols-2 gap-4 animate-pulse">
                    {[...Array(4)].map((_, i) => (
                      <div key={i} className="h-20 bg-gray-100 rounded-2xl" />
                    ))}
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 bg-slate-50 rounded-2xl text-center">
                      <p className="text-2xl font-black text-slate-800">
                        {progress?.total_articles_read ?? 0}
                      </p>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                        Articles Read
                      </p>
                    </div>
                    <div className="p-4 bg-slate-50 rounded-2xl text-center">
                      <p className="text-2xl font-black text-slate-800">
                        {progress?.total_quizzes_taken ?? 0}
                      </p>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                        Quizzes Taken
                      </p>
                    </div>
                    <div className="p-4 bg-orange-50 rounded-2xl text-center">
                      <p className="text-2xl font-black text-orange-600 flex items-center justify-center gap-1">
                        <Flame className="h-5 w-5" />
                        {progress?.current_streak ?? 0}
                      </p>
                      <p className="text-[10px] font-bold text-orange-400 uppercase tracking-wider">
                        Day Streak
                      </p>
                    </div>
                    <div className="p-4 bg-slate-50 rounded-2xl text-center">
                      <p className="text-2xl font-black text-slate-800">
                        {progress
                          ? `${progress.syllabus_coverage_percent.toFixed(1)}%`
                          : "—"}
                      </p>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                        Syllabus Coverage
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
