import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";

// Serves the shared-secret token to the same-origin browser bundle.
// The token lives in ~/.reciter-desktop/api-token, written by the
// FastAPI process on first start. Other localhost origins cannot read
// this route (CORS would block them), so the token stays scoped to this
// Next.js install.

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const TOKEN_PATH = path.join(homedir(), ".reciter-desktop", "api-token");

export async function GET() {
  try {
    const token = (await fs.readFile(TOKEN_PATH, "utf8")).trim();
    if (!token) {
      return NextResponse.json(
        { error: "Token file is empty — start the backend first." },
        { status: 503 }
      );
    }
    return NextResponse.json(
      { token },
      { headers: { "Cache-Control": "no-store" } }
    );
  } catch (err: unknown) {
    const code = (err as NodeJS.ErrnoException)?.code;
    if (code === "ENOENT") {
      return NextResponse.json(
        { error: "Token file not found — start the backend first." },
        { status: 503 }
      );
    }
    return NextResponse.json(
      { error: "Failed to read token file" },
      { status: 500 }
    );
  }
}
