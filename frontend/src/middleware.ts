import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy all /api/* requests to the Django backend.
 *
 * Next.js "rewrites" in next.config.js do NOT work in standalone mode,
 * so we use middleware to proxy API requests via fetch.
 */
export async function middleware(request: NextRequest) {
  const backendUrl =
    process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";

  // Build the target URL
  const path = request.nextUrl.pathname;
  const search = request.nextUrl.search;
  const target = `${backendUrl}${path}${search}`;

  // Forward headers (except host)
  const headers = new Headers(request.headers);
  headers.delete("host");

  try {
    const backendResponse = await fetch(target, {
      method: request.method,
      headers,
      body:
        request.method !== "GET" && request.method !== "HEAD"
          ? await request.blob()
          : undefined,
      // @ts-ignore — Next.js specific
      duplex: "half",
    });

    // Build response with backend's status, headers, and body
    const responseHeaders = new Headers(backendResponse.headers);
    // Remove transfer-encoding since we're re-sending
    responseHeaders.delete("transfer-encoding");

    return new NextResponse(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error(`[Middleware] Proxy error for ${target}:`, error);
    return NextResponse.json(
      { error: "Backend unavailable", detail: String(error) },
      { status: 502 }
    );
  }
}

export const config = {
  matcher: "/api/:path*",
};
