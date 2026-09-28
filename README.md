# cnki-batch-download

Bulk-download papers from CNKI (中国知网) as PDFs, by criteria: sort by citation count or
relevance, filter by journal, author or year, save the top N. Runs through a real browser
profile that keeps one login, so it works with a personal account as well as a university one.

Three pieces:

- `skill/cnki-batch-download/` — search by criteria → confirm a shortlist → download
- `skill/cnki-download/` — save a single paper
- `patch_cnki_mcp.py` — plumbing: makes [`cnki-mcp`](https://github.com/NoFixedPoint/cnki-mcp)
  survive CNKI's captcha and article pages, which unpatched it does not

## Install

```bash
pip install git+https://github.com/NoFixedPoint/cnki-mcp.git
python -m playwright install chromium
python patch_cnki_mcp.py
cp -r skill/* ~/.claude/skills/     # Claude Code's skills dir; other agents differ
claude mcp add cnki -- cnki-mcp     # Claude Code
```

The last two lines are Claude Code syntax; other agents register MCP servers their own way.

If the registration fails, `cnki-mcp` is not on `PATH` — pip's user-script directory often
isn't. Print its real location and register that path instead:

```bash
python -c "import shutil; print(shutil.which('cnki-mcp'))"
claude mcp add cnki -- <that path>   # Claude Code
```

**In mainland China** the first two lines can fail intermittently — GitHub and the Playwright
CDN are sometimes unreachable. PyPI and the npm registry are not affected. If a step dies
with a connection reset or a timeout, retry it, or point `HTTPS_PROXY` at a local proxy for
that command.

Requires Python 3.10+ and a CNKI account with access to the papers you want — institutional
or personal. Nothing here grants access you do not already have.

Works on Windows, macOS and Linux: the script is plain Python and the profile lives at
`~/.cnki-mcp/chrome-profile`. The only platform-specific caveat is the Windows drive-root note
in Notes.

## What you do by hand

An agent can run every command above; two things it cannot:

1. **Restart it** afterwards, so the new MCP server loads.
2. **Pass the first-run handshake.** The first search opens a Chromium window — log in to
   CNKI there if your access is account-based, and slide the captcha. An agent cannot solve
   a slider.

Both stick: that window is a real persistent browser profile, so later searches and downloads
need nothing from you. Expect to redo the handshake after a long idle gap, or whenever CNKI
expires the session — not on every run.

## Use

Plain language — the criteria come from the conversation, not from a config file:

> 搜「数字人民币 跨境支付」，按被引排序，限《金融研究》和《经济研究》，2019 年以后，下前 15 篇到 D:\Research\papers

> Download the top 20 most-cited papers on RMB internationalization.

`search_cnki` already exposes `sort` (被引 / 相关度 / 发表时间 / 下载 / 综合), `journal`,
`author` and `pages`, so "sort by citations and take the top N" needs no code.

## Why the patch

Unpatched `cnki-mcp` cannot download at all:

- **Captcha** — headless browser, fresh context per request, so nothing persists and
  CNKI's slider fires on every call. Fixed with a visible window and a persistent profile,
  so one solve sticks.
- **Article pages** — all 11 `page.goto(...)` use `wait_until="load"`, which never fires on
  CNKI pages because they pull third-party resources that never finish; `goto()` times out
  at 30 s. Fixed with `domcontentloaded` and a 60 s timeout.

`patch_cnki_mcp.py` edits your installed module in place — no fork, no redistribution. It
backs the original up to `.orig`, applies each patch only if absent, and refuses to write
anything that does not compile:

```bash
python patch_cnki_mcp.py            # patch
python patch_cnki_mcp.py --check    # report status
python patch_cnki_mcp.py --restore  # revert
```

Both stealth flags were already in upstream; this patch adds no evasion — it removes
user-agent rotation.

## Options

| Variable | Default | Purpose |
|---|---|---|
| `CNKI_MCP_HEADLESS` | `false` | Keep `false` so you can solve the captcha. |
| `CNKI_MCP_USER_DATA_DIR` | `~/.cnki-mcp/chrome-profile` | Where the persistent profile lives. |

## Limits

Enforced by the batch skill, not optional: **≤ 20 papers per run**, one run at a time,
**3–6 s between downloads**, and a shortlist-confirm step before anything is fetched. CNKI
accounts have download quotas, and bulk downloading is the behaviour most likely to breach
CNKI's terms and to get a shared institutional IP range — or your own account — rate-limited.
Keep batches small.

## Notes

- **Re-apply after upgrading `cnki-mcp`** — `pip install` overwrites the module and
  silently reverts the patch. Run `--check`.
- **The profile holds your CNKI login.** `~/.cnki-mcp/chrome-profile` is a credential; do
  not sync or commit it. (`.gitignore` excludes it.)
- **Download paths must be writable.** On Windows, a folder in a drive root (`D:\papers`)
  fails with `[WinError 5]`; use a path inside an existing folder.

## License

MIT — see [LICENSE](LICENSE). `cnki-mcp` is MIT, © NoFixedPoint; no code from it is
redistributed here.

---

按条件批量下载知网论文：按被引或相关度排序，限定期刊、作者、年份，存前 N 篇为 PDF。通过真实浏览器 profile 运行，校内外一致；机构账号或个人账号均可。批量默认限速、每批 ≤ 20 篇，请勿过量抓取以免账号或机构 IP 被限流。
