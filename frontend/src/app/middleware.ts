import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Next.js Middleware
 *
 * Currently a pass-through. Auth is handled client-side via localStorage tokens.
 * This file is kept for future server-side route protection (e.g., cookie-based auth).
 *
 * To enable protection, set auth cookies on login and uncomment the guard below.
 */
export function middleware(_request: NextRequest) {
  // Future: check for auth cookie and redirect to /auth/login if missing
  // const token = request.cookies.get('access_token');
  // const protectedPaths = ['/dashboard', '/notebook', '/assessment'];
  // const isProtected = protectedPaths.some(p => request.nextUrl.pathname.startsWith(p));
  // if (isProtected && !token) {
  //   return NextResponse.redirect(new URL('/auth/login', request.url));
  // }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static, _next/image (Next.js internals)
     * - favicon.ico
     * - public files
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
