/**
 * Dev-only middleware: lists cache runs and streams media under the repo root.
 */
import fs, { globSync } from "node:fs"
import fsPromises from "node:fs/promises"
import type http from "node:http"
import path from "node:path"

import type { Connect } from "vite"

/** Normalize and ensure path is inside project root (paths must exist after resolution). */
function resolveUnderRepoRoot(repoRootAbs: string, requestedPath: string): string | null {
  try {
    if (!requestedPath.trim()) return null
    const abs = path.isAbsolute(requestedPath)
      ? path.normalize(requestedPath)
      : path.normalize(path.resolve(repoRootAbs, requestedPath))
    const repoReal = fs.realpathSync(repoRootAbs)
    const resolvedReal =
      typeof fs.realpathSync.native === "function" ? fs.realpathSync.native(abs) : fs.realpathSync(abs)
    if (resolvedReal !== repoReal && !resolvedReal.startsWith(repoReal + path.sep)) {
      return null
    }
    return resolvedReal
  } catch {
    return null
  }
}

function extMime(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase()
  switch (ext) {
    case ".mp4":
      return "video/mp4"
    case ".mov":
      return "video/quicktime"
    case ".webm":
      return "video/webm"
    case ".mkv":
      return "video/x-matroska"
    default:
      return "application/octet-stream"
  }
}

async function readJson(analysisPath: string): Promise<{ analyzedAt: string | null; clipCount: number } | null> {
  try {
    const raw = await fsPromises.readFile(analysisPath, "utf8")
    const parsed = JSON.parse(raw) as { analyzedAt?: string; clips?: unknown[] }
    const clipCount = Array.isArray(parsed.clips) ? parsed.clips.length : 0
    return {
      analyzedAt: typeof parsed.analyzedAt === "string" ? parsed.analyzedAt : null,
      clipCount,
    }
  } catch {
    return null
  }
}

function sendJson(res: http.ServerResponse, status: number, body: unknown) {
  const data = JSON.stringify(body)
  res.statusCode = status
  res.setHeader("Content-Type", "application/json; charset=utf-8")
  res.setHeader("Content-Length", Buffer.byteLength(data))
  res.end(data)
}

function sendText(res: http.ServerResponse, status: number, message: string) {
  res.statusCode = status
  res.setHeader("Content-Type", "text/plain; charset=utf-8")
  res.end(message)
}

/** Under ``runDir``, first ``vlm-analysis.json`` from ``globSync`` (order is not guaranteed). */
function findVlmAnalysisPath(runDir: string): string | null {
  let matches: string[]
  try {
    matches = globSync("**/vlm-analysis.json", { cwd: runDir })
  } catch {
    return null
  }
  if (matches.length === 0) return null
  return path.join(runDir, matches[0])
}

export function createCacheApiMiddleware(repoRootAbs: string): Connect.NextHandleFunction {
  return (req, res, next) => {
    const url = req.url
    if (!url?.startsWith("/api/")) {
      next()
      return
    }

    const parsed = new URL(url, "http://127.0.0.1")

    if (parsed.pathname === "/api/runs" && req.method === "GET") {
      void (async () => {
        const cacheDir = path.join(repoRootAbs, "cache")
        let entries: fs.Dirent[]
        try {
          entries = await fsPromises.readdir(cacheDir, { withFileTypes: true })
        } catch {
          sendJson(res, 200, [])
          return
        }

        const runs: Array<{ runId: string; analyzedAt: string | null; clipCount: number }> = []
        for (const dirent of entries) {
          if (!dirent.isDirectory()) continue
          const analysisPath = findVlmAnalysisPath(path.join(cacheDir, dirent.name))
          if (!analysisPath) continue
          const meta = await readJson(analysisPath)
          if (!meta) continue
          runs.push({
            runId: dirent.name,
            analyzedAt: meta.analyzedAt,
            clipCount: meta.clipCount,
          })
        }
        runs.sort((a, b) => (a.runId < b.runId ? 1 : a.runId > b.runId ? -1 : 0))
        sendJson(res, 200, runs)
      })().catch(() => sendText(res, 500, "failed to list runs"))
      return
    }

    const runMatch = /^\/api\/run\/([^/]+)\/analysis$/.exec(parsed.pathname)
    if (runMatch?.[1] && req.method === "GET") {
      const runId = decodeURIComponent(runMatch[1])
      if (runId.includes("..")) {
        sendText(res, 400, "bad run id")
        return
      }
      const runDir = path.resolve(repoRootAbs, "cache", runId)
      const analysisPath = findVlmAnalysisPath(runDir)
      const resolved = analysisPath ? resolveUnderRepoRoot(repoRootAbs, analysisPath) : null
      if (!resolved || !fs.existsSync(resolved)) {
        sendText(res, 404, "analysis not found")
        return
      }
      void fsPromises
        .readFile(resolved, "utf8")
        .then((body) => {
          res.statusCode = 200
          res.setHeader("Content-Type", "application/json; charset=utf-8")
          res.end(body)
        })
        .catch(() => sendText(res, 500, "read failed"))
      return
    }

    if (parsed.pathname === "/api/media" && req.method === "GET") {
      const p = parsed.searchParams.get("p")
      if (!p) {
        sendText(res, 400, "missing p")
        return
      }
      let decoded: string
      try {
        decoded = decodeURIComponent(p)
      } catch {
        sendText(res, 400, "bad encoding")
        return
      }
      const absPath = resolveUnderRepoRoot(repoRootAbs, decoded)
      if (!absPath || !fs.existsSync(absPath) || !fs.statSync(absPath).isFile()) {
        sendText(res, 404, "not found")
        return
      }

      const mime = extMime(absPath)
      const stat = fs.statSync(absPath)
      const size = stat.size
      res.setHeader("Accept-Ranges", "bytes")
      res.setHeader("Content-Type", mime)

      const range = req.headers.range
      if (range) {
        const m = /^bytes=(\d*)-(\d*)$/.exec(range)
        if (m) {
          const start = m[1] ? Number.parseInt(m[1], 10) : 0
          const endPart = m[2] ? Number.parseInt(m[2], 10) : size - 1
          const end = Math.min(endPart, size - 1)
          if (!Number.isNaN(start) && !Number.isNaN(end) && start <= end && start < size) {
            res.statusCode = 206
            const chunk = end - start + 1
            res.setHeader("Content-Range", `bytes ${start}-${end}/${size}`)
            res.setHeader("Content-Length", String(chunk))
            const stream = fs.createReadStream(absPath, { start, end })
            stream.pipe(res)
            stream.on("error", () => {
              if (!res.headersSent) sendText(res, 500, "stream error")
              else res.destroy()
            })
            return
          }
        }
      }

      res.statusCode = 200
      res.setHeader("Content-Length", String(size))
      const stream = fs.createReadStream(absPath)
      stream.pipe(res)
      stream.on("error", () => {
        if (!res.headersSent) sendText(res, 500, "stream error")
        else res.destroy()
      })
      return
    }

    next()
  }
}
