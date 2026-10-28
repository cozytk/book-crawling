import { NextRequest } from "next/server";

export const maxDuration = 60;
export const dynamic = "force-dynamic";

async function proxy(request: NextRequest) {
  const base = process.env.API_BACKEND_URL || "http://127.0.0.1:8000";
  const pathname = request.nextUrl.pathname;
  const allowed = /^\/api\/(search(?:\/stream|\/check|\/[0-9a-f-]+)?|searches|platforms|health)$/;
  if (!allowed.test(pathname)) return new Response("Not Found", { status: 404 });

  try {
    const upstream = await fetch(`${base}${pathname}${request.nextUrl.search}`, {
      method: request.method,
      headers: {
        "Content-Type": "application/json",
        "x-api-token": process.env.API_SERVICE_TOKEN || "",
      },
      body: request.method === "POST" ? await request.text() : undefined,
      cache: "no-store",
      signal: request.signal,
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("Content-Type") || "application/json",
        "Cache-Control": "private, no-store",
        "X-Accel-Buffering": "no",
      },
    });
  } catch {
    console.error("Book search API connection failed");
    return Response.json({ detail: "검색 서버에 연결하지 못했습니다. 잠시 후 다시 시도해주세요." }, { status: 502 });
  }
}

export { proxy as GET, proxy as POST };
