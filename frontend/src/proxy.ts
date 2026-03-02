import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value;
  const { pathname } = request.nextUrl;

  // Protected routes
  const protectedPaths = [
    "/profile",
    "/assessment",
    "/articles/my-notebook",
    "/generate",
  ];
  const isProtected = protectedPaths.some((path) => pathname.startsWith(path));

  if (isProtected && !token) {
    return NextResponse.redirect(new URL("/auth/login", request.url));
  }

  // Auth routes (redirect if already logged in)
  const authPaths = ["/auth/login", "/auth/register"];
  const isAuthPath = authPaths.some((path) => pathname.startsWith(path));

  if (isAuthPath && token) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/profile/:path*",
    "/auth/:path*",
    "/assessment/:path*",
    "/articles/my-notebook",
    "/generate/:path*",
  ],
};
