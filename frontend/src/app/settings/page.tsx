/**
 * Settings Page
 */

"use client";

import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Bell, Lock, User, Palette, Shield } from "lucide-react";

export default function SettingsPage() {
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
          <div className="hidden lg:block space-y-1">
            <button className="w-full flex items-center gap-3 px-4 py-2 bg-blue-50 text-blue-700 rounded-lg font-bold text-sm">
              <User className="h-4 w-4" />
              General
            </button>
            <button className="w-full flex items-center gap-3 px-4 py-2 text-gray-600 hover:bg-gray-50 rounded-lg font-semibold text-sm">
              <Lock className="h-4 w-4" />
              Security
            </button>
            <button className="w-full flex items-center gap-3 px-4 py-2 text-gray-600 hover:bg-gray-50 rounded-lg font-semibold text-sm">
              <Bell className="h-4 w-4" />
              Notifications
            </button>
            <button className="w-full flex items-center gap-3 px-4 py-2 text-gray-600 hover:bg-gray-50 rounded-lg font-semibold text-sm">
              <Palette className="h-4 w-4" />
              Appearance
            </button>
          </div>

          {/* Settings Sections */}
          <div className="lg:col-span-3 space-y-8">
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-6">
              <h3 className="font-bold text-lg flex items-center gap-2">
                <Shield className="h-5 w-5 text-blue-600" />
                Security Settings
              </h3>

              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="current-pass">Current Password</Label>
                  <Input
                    id="current-pass"
                    type="password"
                    placeholder="••••••••"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="new-pass">New Password</Label>
                    <Input
                      id="new-pass"
                      type="password"
                      placeholder="••••••••"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="confirm-pass">Confirm New Password</Label>
                    <Input
                      id="confirm-pass"
                      type="password"
                      placeholder="••••••••"
                    />
                  </div>
                </div>
              </div>

              <Button className="bg-blue-600 hover:bg-blue-700">
                Update Password
              </Button>
            </div>

            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-6">
              <h3 className="font-bold text-lg">Notifications</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-sm">Email Reports</p>
                    <p className="text-xs text-gray-500">
                      Weekly summary of your learning progress.
                    </p>
                  </div>
                  <div className="h-5 w-10 bg-blue-600 rounded-full relative">
                    <div className="absolute right-1 top-1 h-3 w-3 bg-white rounded-full" />
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-sm">Orbit Alerts</p>
                    <p className="text-xs text-gray-500">
                      Get notified when new articles are generated for your
                      topics.
                    </p>
                  </div>
                  <div className="h-5 w-10 bg-gray-200 rounded-full relative">
                    <div className="absolute left-1 top-1 h-3 w-3 bg-white rounded-full" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
