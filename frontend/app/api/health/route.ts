import { NextResponse } from "next/server";

export function GET() {
  return NextResponse.json({
    ok: true,
    service: "frontend",
    mode: process.env.NODE_ENV || "development",
  });
}
