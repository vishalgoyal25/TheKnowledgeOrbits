/**
 * Profile Page
 */

"use client";

import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { useAuth } from "@/lib/auth/useAuth";
import { User, Mail, Calendar, ShieldCheck, BadgeCheck } from "lucide-react";

export default function ProfilePage() {
  const { user } = useAuth();

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto p-6 lg:p-12">
        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
          {/* Header/Cover */}
          <div className="h-32 bg-gradient-to-r from-blue-600 to-indigo-700" />

          <div className="px-8 pb-8">
            {/* Avatar Overlap */}
            <div className="relative -mt-12 mb-6">
              <div className="h-24 w-24 rounded-2xl bg-white p-1 shadow-lg">
                <div className="h-full w-full rounded-xl bg-blue-100 flex items-center justify-center text-3xl font-black text-blue-600 uppercase">
                  {user?.full_name?.charAt(0) || user?.email?.charAt(0)}
                </div>
              </div>
              <div
                className="absolute bottom-0 left-20 bg-green-500 border-4 border-white h-6 w-6 rounded-full shadow-sm"
                title="Online"
              />
            </div>

            <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">
                  {user?.full_name || "Aspirant"}
                </h1>
                <p className="text-gray-500 font-medium flex items-center gap-2 mt-1">
                  <Mail className="h-4 w-4" />
                  {user?.email}
                </p>
              </div>
              <div className="flex items-center gap-2 px-4 py-2 bg-blue-50 text-blue-700 rounded-xl font-bold text-sm">
                <BadgeCheck className="h-4 w-4" />
                Pro Member
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-12">
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
                        February 2026
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
                      <p className="text-sm font-semibold text-green-600 flex items-center gap-1">
                        Verified & Active
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-6">
                <h3 className="text-lg font-bold text-gray-800 border-b pb-2">
                  Learning Stats
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-slate-50 rounded-2xl text-center">
                    <p className="text-2xl font-black text-slate-800">12</p>
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                      Articles Read
                    </p>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-2xl text-center">
                    <p className="text-2xl font-black text-slate-800">85%</p>
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                      Avg Score
                    </p>
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
