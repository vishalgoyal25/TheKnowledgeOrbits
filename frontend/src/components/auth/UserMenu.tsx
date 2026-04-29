"use client";

import { useAuth } from "@/lib/auth/useAuth";
import { getProfile } from "@/lib/api/userstate";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { User, LogOut, Settings, LayoutDashboard } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function UserMenu() {
  const { user, logout } = useAuth();
  const [avatarUrl, setAvatarUrl] = useState<string>("");

  useEffect(() => {
    if (!user) return;
    getProfile()
      .then((p) => setAvatarUrl(p.avatar_url || ""))
      .catch(() => {});
  }, [user]);

  if (!user) return null;

  const initial = (
    user.full_name?.charAt(0) || user.email.charAt(0)
  ).toUpperCase();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="relative h-8 w-8 rounded-full p-0">
          <div className="relative h-8 w-8 rounded-full overflow-hidden bg-blue-100 flex items-center justify-center transition-transform hover:scale-110">
            {avatarUrl ? (
              <Image
                src={avatarUrl}
                alt={user.full_name || "Avatar"}
                fill
                className="object-cover rounded-full"
                sizes="32px"
              />
            ) : (
              <span className="text-blue-600 font-bold uppercase text-sm select-none">
                {initial}
              </span>
            )}
          </div>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align="end" forceMount>
        <DropdownMenuLabel className="font-normal">
          <div className="flex items-center gap-3">
            <div className="relative h-9 w-9 rounded-full overflow-hidden bg-blue-100 flex-shrink-0 flex items-center justify-center">
              {avatarUrl ? (
                <Image
                  src={avatarUrl}
                  alt={user.full_name || "Avatar"}
                  fill
                  className="object-cover rounded-full"
                  sizes="36px"
                />
              ) : (
                <span className="text-blue-600 font-bold uppercase text-sm select-none">
                  {initial}
                </span>
              )}
            </div>
            <div className="flex flex-col space-y-0.5">
              <p className="text-sm font-medium leading-none">
                {user.full_name}
              </p>
              <p className="text-xs leading-none text-muted-foreground">
                {user.email}
              </p>
            </div>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link
            href="/dashboard"
            className="cursor-pointer w-full flex items-center"
          >
            <LayoutDashboard className="mr-2 h-4 w-4" />
            <span>Dashboard</span>
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link
            href="/profile"
            className="cursor-pointer w-full flex items-center"
          >
            <User className="mr-2 h-4 w-4" />
            <span>Profile</span>
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link
            href="/settings"
            className="cursor-pointer w-full flex items-center"
          >
            <Settings className="mr-2 h-4 w-4" />
            <span>Settings</span>
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-red-600 cursor-pointer w-full flex items-center focus:text-red-600"
          onClick={() => logout()}
        >
          <LogOut className="mr-2 h-4 w-4" />
          <span>Log out</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
