import { tool } from "@opencode-ai/plugin"

// App Portal auto-registration tool.
//
// Register a web app created in this OpenCode session into the portal's app
// list, pinning the current session so feedback submitted on the portal can be
// injected here without opening the session manually.
//
// Required environment:
//   PORTAL_APP_URL    base URL of the portal (default http://localhost:8000)
//   PORTAL_APP_TOKEN  a control-plane device bearer token (tk_...)
//
// Deploy by symlinking/copying this file into ~/.config/opencode/tools/app_portal.ts
// (the tool name becomes app_portal_register).

const PORTAL_URL = (process.env.PORTAL_APP_URL ?? "http://localhost:8000").replace(/\/$/, "")
const PORTAL_TOKEN = process.env.PORTAL_APP_TOKEN ?? ""

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
}

export const register = tool({
  description:
    "Register this project's web app in the portal app list (POST /api/app-portal/apps), pinning the current OpenCode session. Requires PORTAL_APP_URL and PORTAL_APP_TOKEN.",
  args: {
    name: tool.schema.string().describe("App display name"),
    description: tool.schema.string().optional().describe("Short description"),
    url: tool.schema.string().optional().describe("Public URL where the app is served"),
    slug: tool.schema.string().optional().describe("URL slug (defaults to slugified name)"),
    tags: tool.schema.string().optional().describe("Comma-separated tags"),
  },
  async execute(args, ctx) {
    if (!PORTAL_TOKEN) {
      return JSON.stringify({ status: "error", message: "PORTAL_APP_TOKEN is not set" })
    }
    const directory = ctx.worktree || ctx.directory
    const tags = String(args.tags ?? "")
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean)
    const body = {
      name: args.name,
      description: args.description,
      url: args.url,
      slug: args.slug || slugify(args.name),
      project_directory: directory,
      opencode_session_id: ctx.sessionID,
      source: "opencode",
      tags,
    }
    try {
      const res = await fetch(`${PORTAL_URL}/api/app-portal/apps`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${PORTAL_TOKEN}`,
        },
        body: JSON.stringify(body),
      })
      const text = await res.text()
      if (!res.ok) {
        return JSON.stringify({ status: "error", http: res.status, message: text })
      }
      const data = JSON.parse(text)
      return JSON.stringify({
        status: "ok",
        slug: data.slug,
        session_id: data.opencode_session_id,
        webui_url: data.webui_url,
      })
    } catch (e: any) {
      return JSON.stringify({ status: "error", message: e?.message ?? String(e) })
    }
  },
})
