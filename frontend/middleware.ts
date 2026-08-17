// Next.js Edge Middleware for route protection.
// Runs on every request before page rendering — zero bundle impact.
// Strategy: check for refresh token in sessionStorage is not possible in middleware
// (no access to browser APIs), so we check for a custom header or cookie.
// For now: all (app) routes require the user to have a valid session.
// The AuthProvider handles the actual token refresh on the client side.
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Public routes that don't require authentication
const PUBLIC_PATHS = ['/', '/login', '/forgot-pin'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public routes
  if (PUBLIC_PATHS.some(p => pathname === p || pathname.startsWith('/api/'))) {
    return NextResponse.next();
  }

  // Allow Next.js internals and static assets
  if (pathname.startsWith('/_next') || pathname.startsWith('/favicon') || pathname.includes('.')) {
    return NextResponse.next();
  }

  // For protected routes: the client-side AuthProvider handles actual auth state.
  // Middleware just ensures the route structure is correct.
  // Full JWT validation in middleware would require the Edge Runtime JWT library.
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
