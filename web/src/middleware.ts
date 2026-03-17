import { NextRequest, NextResponse } from "next/server";

const TOKEN_PARAM = "token";
const COOKIE_NAME = "book-crawler-auth";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 year

export function middleware(request: NextRequest) {
  const { searchParams, pathname } = request.nextUrl;
  const secret = process.env.ACCESS_TOKEN;

  // No secret configured → open access (local dev)
  if (!secret) return NextResponse.next();

  // Token in URL → set cookie and redirect to clean URL
  const token = searchParams.get(TOKEN_PARAM);
  if (token === secret) {
    const url = request.nextUrl.clone();
    url.searchParams.delete(TOKEN_PARAM);
    const res = NextResponse.redirect(url);
    res.cookies.set(COOKIE_NAME, secret, {
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      maxAge: COOKIE_MAX_AGE,
      path: "/",
    });
    return res;
  }

  // Valid cookie → allow
  if (request.cookies.get(COOKIE_NAME)?.value === secret) {
    return NextResponse.next();
  }

  // Health check for monitoring (no auth needed)
  if (pathname === "/api/health") {
    return NextResponse.next();
  }

  // Unauthorized → 404 (don't reveal the site exists)
  return new NextResponse("Not Found", { status: 404 });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
