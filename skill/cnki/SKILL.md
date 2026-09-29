---
name: cnki
description: >-
  Search CNKI (中国知网) and save paper PDFs through the cnki-mcp MCP server — one
  specific paper ("download this paper", "把这篇知网论文下载下来", "save this PDF to ...",
  or a title/链接 you were given), or many at once by criteria ("批量下载", "把这批论文都
  下下来", "按被引排序下载前 20 篇", "download the top 20 cited papers on X",
  "把《经济研究》上关于 X 的论文都下下来"). Use whenever the user wants CNKI papers on disk
  — a single PDF, a shortlist, or a citation-ranked top-N. Requires a patched cnki-mcp and
  legitimate CNKI access.
---

# CNKI → PDF

One pipeline, two modes: **single paper** (§2) or **batch by criteria** (§3). Both search
CNKI for a short `label`, then call `download_paper_pdf`.

## 0. Prerequisites

- `cnki-mcp` installed **and patched** — the patch is required. Unpatched, `cnki-mcp` times
  out on every article page and cannot download at all. See this repository's
  `patch_cnki_mcp.py`.
- A CNKI account with access to the paper(s). Neither the patch nor this skill grants access
  you do not already have.

## 1. Get a label

Downloads are addressed by the short `label` that `search_cnki` returns — **never by URL**.

- **Title only** → `find_best_match(title)`, then confirm it is the right paper.
- **Topic / keyword** → `search_cnki(query, ...)` and pick from `papers[].label`.
- **Label already seen earlier in this session** → reuse it directly.

For the full set of `search_cnki` parameters, see §3.1.

## 2. Single paper

```
download_paper_pdf(paper=<label>, save_dir=<absolute path>)
```

`save_dir` must be an **absolute path**; the call creates the directory. Then verify (§4).

## 3. Batch by criteria

### 3.1 Turn the request into parameters

The criteria live in the conversation, never in this file. If the user has not stated them,
ask — but ask **once, in one batch**, and write the answers down.

| Criterion | `search_cnki` parameter | Notes |
|---|---|---|
| Topic | `query` | topic/keyword/title only — **never put an author in here** |
| Search field | `search_type` | `主题` (default) / `关键词` / `篇名` / `DOI` |
| Author | `author` | separate parameter; combines with `query` |
| Journal | `journal` | exact match; join several with `+`, e.g. `经济研究+管理世界` |
| Sort | `sort` | `被引` / `相关度` (default) / `发表时间` / `下载` / `综合` |
| Depth | `pages` | 1–10 pages of results |
| How many to save | — | cap it; see §3.4 |
| Year floor / citation floor | — | filter the returned list yourself |

`sort='被引'` for influence ranking, `'相关度'` for topical fit, `'发表时间'` for the newest work.

### 3.2 Shortlist, then confirm

Show the shortlist as a compact table (`label` / title / source / year / citations) and say
which you intend to fetch. **Download only after the user confirms** — unless they already
said "just download", in which case state the count and proceed.

### 3.3 Download, slowly

For each chosen label: `download_paper_pdf(paper=<label>, save_dir=<absolute path>)`, then
verify (§4).

- **Wait 3–6 seconds between downloads.** The server already jitters its own internal
  requests; this is *on top*. It is the main thing keeping the account and the institution's
  IP range off CNKI's radar.
- **Report** any paper that returns no `file_path` (no PDF, or no access) as skipped — do not
  retry it.
- **Stop the whole run on the first unexpected error** (session lost, captcha wall, permission
  error) and report how far you got. Do not grind through failures.

### 3.4 Limits — these are not suggestions

- **≤ 20 papers per run.** For more, do a second run after the user reviews the first. Never
  one long unattended loop.
- **One run at a time.** Chromium locks the profile directory; a concurrent run fails.
- **Respect the account's download quota.** CNKI accounts have per-period caps, and a batch can
  exhaust one quickly. If the user has not mentioned their quota, ask.

## 4. Verify every file

On success the result has `file_path`. Confirm the bytes actually are a PDF:

```bash
head -c 5 "<file_path>"   # must print %PDF-
```

A file that is missing, empty, or starts with `<` is an HTML error page, not a paper.

## 5. Pitfalls that actually bite

- **`save_dir` must be absolute and writable.** On Windows, creating a folder directly in a
  drive root (`D:\papers`) fails with `PermissionError: [WinError 5]`. Use a path inside an
  existing folder, e.g. `D:\Research\papers`.
- **The first run blocks on a captcha by design.** A visible Chromium window opens and CNKI
  shows a slider. Wait for the user to slide it — do not treat the pause as a hang and do not
  retry. The session persists, so this is rare rather than per-call — but it returns after a
  long idle gap.
- **A missing PDF button is a real answer.** The server reports "PDF下载按钮未找到" when the
  paper has no PDF, or when your account has no access to it. Report that as the outcome rather
  than retrying.
- **CNKI supplies the filename**, via `Content-Disposition`, and it often contains Chinese
  punctuation. Leave it alone; renaming risks encoding damage for no gain.
- **`get_paper_bibtex(label)`** returns a BibTeX entry for any label, if the user wants the
  citation alongside the file(s).

## 6. Report

Finish with a table — saved (label, title, absolute path, size) and skipped (label, title,
reason) — plus the total count and the absolute save directory so the user can open it.

## On responsible use

Bulk automated downloading is the behaviour most likely to breach CNKI's terms of service and
to get a shared institutional IP range (or your own account) rate-limited. That is why §3.4 is
written as hard rules rather than as advice — if you fork this, keep them.
