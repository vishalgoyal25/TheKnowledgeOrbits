"use client";

/**
 * Settings Page — fully wired (Phase G, FEATURES7)
 *
 * Sections:
 *   - General  : display name + bio (PATCH /userstate/profile/update/)
 *   - Security : change password   (POST /auth/change-password/)
 *   - Notifications: email prefs   (GET/PATCH /userstate/preferences/)
 */

import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { authAPI } from "@/lib/api/auth";
import {
  getPreferences,
  getProfile,
  updatePreferences,
  updateProfile,
  type UserPreferences,
  type UserProfile,
} from "@/lib/api/userstate";
import {
  Bell,
  CheckCircle2,
  Loader2,
  Lock,
  Palette,
  Save,
  Shield,
  User,
} from "lucide-react";
import { useEffect, useState } from "react";

// ── Section IDs ───────────────────────────────────────────────────────────────

type Section = "general" | "security" | "notifications" | "appearance";

const NAV: { id: Section; label: string; icon: React.ReactNode }[] = [
  { id: "general", label: "General", icon: <User className="h-4 w-4" /> },
  { id: "security", label: "Security", icon: <Lock className="h-4 w-4" /> },
  {
    id: "notifications",
    label: "Notifications",
    icon: <Bell className="h-4 w-4" />,
  },
  {
    id: "appearance",
    label: "Appearance",
    icon: <Palette className="h-4 w-4" />,
  },
];

// ── Toggle component ──────────────────────────────────────────────────────────

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:opacity-50 ${
        checked ? "bg-blue-600" : "bg-gray-200"
      }`}
    >
      <span
        className={`absolute top-1 h-4 w-4 rounded-full bg-white shadow transition-transform ${
          checked ? "translate-x-6" : "translate-x-1"
        }`}
      />
    </button>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { toast } = useToast();
  const [activeSection, setActiveSection] = useState<Section>("general");

  // ── General ─────────────────────────────────────────────────────────────────
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [generalSaving, setGeneralSaving] = useState(false);

  // ── Security ────────────────────────────────────────────────────────────────
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);

  // ── Notifications ───────────────────────────────────────────────────────────
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [prefsLoading, setPrefsLoading] = useState(true);
  const [prefsSaving, setPrefsSaving] = useState(false);

  // ── Fetch on mount ──────────────────────────────────────────────────────────
  useEffect(() => {
    getProfile()
      .then((p) => {
        setProfile(p);
        setDisplayName(p.full_name ?? "");
        setBio(p.bio ?? "");
      })
      .catch(() =>
        toast({ title: "Could not load profile", variant: "destructive" }),
      )
      .finally(() => setProfileLoading(false));

    getPreferences()
      .then(setPrefs)
      .catch(() => {
        /* non-critical */
      })
      .finally(() => setPrefsLoading(false));
  }, [toast]);

  // ── General save ─────────────────────────────────────────────────────────────
  const handleGeneralSave = async () => {
    setGeneralSaving(true);
    try {
      const updated = await updateProfile({
        full_name: displayName.trim(),
        bio: bio.trim(),
      });
      setProfile(updated);
      toast({ title: "Profile updated ✓" });
    } catch {
      toast({ title: "Failed to update profile", variant: "destructive" });
    } finally {
      setGeneralSaving(false);
    }
  };

  // ── Password save ────────────────────────────────────────────────────────────
  const handlePasswordSave = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      toast({
        title: "All password fields are required",
        variant: "destructive",
      });
      return;
    }
    if (newPassword !== confirmPassword) {
      toast({ title: "New passwords do not match", variant: "destructive" });
      return;
    }
    if (newPassword.length < 8) {
      toast({
        title: "Password must be at least 8 characters",
        variant: "destructive",
      });
      return;
    }
    setPasswordSaving(true);
    try {
      await authAPI.changePassword({
        old_password: currentPassword,
        new_password: newPassword,
        new_password_confirm: confirmPassword,
      });
      toast({ title: "Password updated ✓" });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      const e = err as {
        response?: { data?: { error?: string; old_password?: string[] } };
      };
      const msg =
        e?.response?.data?.error ||
        e?.response?.data?.old_password?.[0] ||
        "Failed to update password";
      toast({ title: msg, variant: "destructive" });
    } finally {
      setPasswordSaving(false);
    }
  };

  // ── Pref toggle ──────────────────────────────────────────────────────────────
  const handlePrefToggle = async (
    key: keyof Omit<UserPreferences, "updated_at">,
    value: boolean,
  ) => {
    if (!prefs) return;
    const optimistic = { ...prefs, [key]: value };
    setPrefs(optimistic);
    setPrefsSaving(true);
    try {
      const updated = await updatePreferences({ [key]: value });
      setPrefs(updated);
    } catch {
      setPrefs(prefs); // revert
      toast({
        title: "Failed to update notification setting",
        variant: "destructive",
      });
    } finally {
      setPrefsSaving(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto p-6 lg:p-12 space-y-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
          <p className="text-gray-500 mt-1">
            Manage your account preferences and security.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Sidebar Nav */}
          <nav className="hidden lg:flex flex-col space-y-1">
            {NAV.map(({ id, label, icon }) => (
              <button
                key={id}
                onClick={() => setActiveSection(id)}
                className={`w-full flex items-center gap-3 px-4 py-2 rounded-lg font-semibold text-sm transition-colors ${
                  activeSection === id
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                {icon}
                {label}
              </button>
            ))}
          </nav>

          {/* Mobile nav pills */}
          <div className="flex lg:hidden gap-2 overflow-x-auto pb-1 col-span-full">
            {NAV.map(({ id, label }) => (
              <button
                key={id}
                onClick={() => setActiveSection(id)}
                className={`flex-shrink-0 px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
                  activeSection === id
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Content Panel */}
          <div className="lg:col-span-3 space-y-6">
            {/* ── General ─────────────────────────────────────────────────── */}
            {activeSection === "general" && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-6">
                <h3 className="font-bold text-lg flex items-center gap-2">
                  <User className="h-5 w-5 text-blue-600" />
                  General
                </h3>

                {profileLoading ? (
                  <div className="space-y-4 animate-pulse">
                    <div className="h-10 bg-gray-100 rounded-lg" />
                    <div className="h-20 bg-gray-100 rounded-lg" />
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="display-name">Display Name</Label>
                      <Input
                        id="display-name"
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        placeholder="Your full name"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="email-display">Email</Label>
                      <Input
                        id="email-display"
                        value={profile?.email ?? ""}
                        disabled
                        className="bg-gray-50 text-gray-400 cursor-not-allowed"
                      />
                      <p className="text-xs text-gray-400">
                        Email cannot be changed here.
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="bio">Bio</Label>
                      <textarea
                        id="bio"
                        value={bio}
                        onChange={(e) => setBio(e.target.value)}
                        rows={3}
                        maxLength={300}
                        placeholder="Tell us a bit about yourself…"
                        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
                      />
                      <p className="text-xs text-gray-400 text-right">
                        {bio.length}/300
                      </p>
                    </div>

                    <Button
                      onClick={handleGeneralSave}
                      disabled={generalSaving}
                      className="bg-blue-600 hover:bg-blue-700 gap-2"
                    >
                      {generalSaving ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4" />
                      )}
                      Save Changes
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* ── Security ────────────────────────────────────────────────── */}
            {activeSection === "security" && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-6">
                <h3 className="font-bold text-lg flex items-center gap-2">
                  <Shield className="h-5 w-5 text-blue-600" />
                  Security
                </h3>

                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="current-pass">Current Password</Label>
                    <Input
                      id="current-pass"
                      type="password"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      placeholder="••••••••"
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="new-pass">New Password</Label>
                      <Input
                        id="new-pass"
                        type="password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        placeholder="••••••••"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="confirm-pass">Confirm Password</Label>
                      <Input
                        id="confirm-pass"
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="••••••••"
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handlePasswordSave();
                        }}
                      />
                    </div>
                  </div>

                  {/* Strength hints */}
                  {newPassword && (
                    <ul className="text-xs space-y-1">
                      {[
                        {
                          ok: newPassword.length >= 8,
                          label: "At least 8 characters",
                        },
                        {
                          ok: /[A-Z]/.test(newPassword),
                          label: "One uppercase letter",
                        },
                        { ok: /[0-9]/.test(newPassword), label: "One number" },
                      ].map(({ ok, label }) => (
                        <li
                          key={label}
                          className={`flex items-center gap-1.5 ${
                            ok ? "text-green-600" : "text-gray-400"
                          }`}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          {label}
                        </li>
                      ))}
                    </ul>
                  )}

                  <Button
                    onClick={handlePasswordSave}
                    disabled={passwordSaving}
                    className="bg-blue-600 hover:bg-blue-700 gap-2"
                  >
                    {passwordSaving ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Lock className="h-4 w-4" />
                    )}
                    Update Password
                  </Button>
                </div>
              </div>
            )}

            {/* ── Notifications ────────────────────────────────────────────── */}
            {activeSection === "notifications" && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-6">
                <h3 className="font-bold text-lg flex items-center gap-2">
                  <Bell className="h-5 w-5 text-blue-600" />
                  Notifications
                </h3>

                {prefsLoading ? (
                  <div className="space-y-4 animate-pulse">
                    {[...Array(3)].map((_, i) => (
                      <div
                        key={i}
                        className="flex justify-between items-center"
                      >
                        <div className="space-y-1">
                          <div className="h-4 w-40 bg-gray-100 rounded" />
                          <div className="h-3 w-64 bg-gray-50 rounded" />
                        </div>
                        <div className="h-6 w-11 bg-gray-100 rounded-full" />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-5">
                    {(
                      [
                        {
                          key: "email_weekly_report" as const,
                          label: "Weekly Report",
                          desc: "Weekly summary of your learning progress sent to your inbox.",
                        },
                        {
                          key: "email_orbit_alerts" as const,
                          label: "Orbit Alerts",
                          desc: "Get notified when new articles are generated for your topics.",
                        },
                        {
                          key: "email_comment_replies" as const,
                          label: "Comment Replies",
                          desc: "Email when someone replies to your comments.",
                        },
                      ] as const
                    ).map(({ key, label, desc }) => (
                      <div
                        key={key}
                        className="flex items-center justify-between gap-4"
                      >
                        <div>
                          <p className="font-semibold text-sm text-gray-800">
                            {label}
                          </p>
                          <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
                        </div>
                        <Toggle
                          checked={prefs?.[key] ?? false}
                          onChange={(v) => handlePrefToggle(key, v)}
                          disabled={prefsSaving}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ── Appearance ───────────────────────────────────────────────── */}
            {activeSection === "appearance" && (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-6">
                <h3 className="font-bold text-lg flex items-center gap-2">
                  <Palette className="h-5 w-5 text-blue-600" />
                  Appearance
                </h3>
                <p className="text-sm text-gray-500">
                  Theme customisation coming soon.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
