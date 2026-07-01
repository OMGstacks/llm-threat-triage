import { NextRequest, NextResponse } from "next/server";

// Per-request Content-Security-Policy with a fresh nonce. Next.js reads the nonce from
// the request-side CSP header and stamps it onto its own framework/hydration scripts, so
// `script-src` needs no 'unsafe-inline' — that's the real XSS mitigation. Inline STYLE
// attributes (this app uses React `style={}`, server-rendered as attributes) can't
// execute script, so `style-src` keeps 'unsafe-inline'. The API proxy and static assets
// are excluded via the matcher below. Adding a nonce opts pages into dynamic rendering,
// which is fine for an authenticated training app.
export function middleware(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const csp = [
    `default-src 'self'`,
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    `style-src 'self' 'unsafe-inline'`,
    `img-src 'self' data: blob:`,
    `font-src 'self'`,
    `connect-src 'self'`,
    `object-src 'none'`,
    `base-uri 'self'`,
    `form-action 'self'`,
    `frame-ancestors 'none'`,
    `upgrade-insecure-requests`,
  ].join("; ");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  // Next reads the nonce from this request-side header to nonce its own scripts.
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  // And the browser enforces it from the response-side header.
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    // Run on pages only — skip the /api proxy, Next's static assets, and public files.
    {
      source: "/((?!api|_next/static|_next/image|favicon.ico|robots.txt).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
