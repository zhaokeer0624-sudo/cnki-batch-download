---
name: cnki-batch-download
description: >-
  Bulk-download CNKI (中国知网) papers as PDFs by criteria — sort by citations or relevance,
  filter by journal, author or year, then save the top N. Use when the user wants many
  CNKI papers at once: "批量下载", "把这批论文都下下来", "按被引排序下载前 20 篇", "download the
  top 20 cited papers on X", "把《经济研究》上关于 X 的论文都下下来". For a single paper use
  cnki-download instead. Requires a patched cnki-mcp and legitimate CNKI access.
---

# Bulk-download CNKI papers

Search CNKI by criteria, pick a shortlist, and save the PDFs. Built on the `cnki-mcp`
MCP server; the sibling `patch_cnki_mcp.py` in this repository is **required** — an
unpatched `cnki-mcp` times out on every article page and cannot download at all.

**Requires:** `cnki-mcp` installed and patched, plus a CNKI account with access to the
papers. Neither the patch nor this skill grants access you do not already have.

## 1. Turn the request into parameters

The criteria live in the conversation, never in this file. If the user has not stated
them, ask — but ask **once, in one batch**, and write the answers down.

| Criterion | `search_cnki` parameter | Notes |
|---|---|---|
| Topic | `query` | topic/keyword/title only — never put an author in here |
| Search field | `search_type` | `主题` (default) / `关键词` / `篇名` / `DOI` |
| Author | `author` | separate parameter; combines with `query` |
| Journal | `journal` | exact match; join several with `+`, e.g. `经济研究+管理世界` |
| Sort | `sort` | `被引` (citations) / `相关度` (relevance, default) / `发表时间` / `下载` / `综合` |
| Depth | `pages` | 1–10 pages of results |
| How many to save | — | cap it; see §4 |
| Year floor / citation floor | — | filter the returned list yourself |

`sort='被引'` for influence ranking, `'相关度'` for topical fit, `'发表时间'` for the newest
work. `search_cnki` returns `papers[]`, each with a short **`label`** — that label, not a
URL, is what the download call takes.

## 2. Shortlist, then confirm

Show the shortlist as a compact table (`label` / title / source / year / citations) and
say which ones you intend to fetch. **Download only after the user confirms** — unless
they already said "just download", in which case state the count and proceed.

## 3. Download, slowly

For each chosen label:

```
download_paper_pdf(paper=<label>, save_dir=<absolute path>)
```

- **Wait 3–6 seconds between downloads.** The server already jitters its own internal
  requests; this is *on top*. It is the main thing keeping the account and the
  institution's IP range off CNKI's radar.
- **Verify each file** starts with `%PDF-`. A missing, empty, or `<`-leading file is an
  HTML error page, not a paper.
- **Report** any paper that returns no `file_path` (no PDF, or no access) as skipped —
  do not retry it.
- **Stop the whole run on the first unexpected error** (session lost, captcha wall,
  permission error) and report how far you got. Do not grind through failures.

### Pitfalls that bite

- **`save_dir` must be absolute and writable.** On Windows, creating a folder directly in
  a drive root (`D:\papers`) fails with `PermissionError: [WinError 5]`; use a path inside
  an existing folder.
- **The first run blocks on a captcha by design.** A visible Chromium window opens and
  CNKI shows a slider. Wait for the user to slide it — do not treat the pause as a hang
  and do not retry. The session persists, so this is rare rather than per-call — but it
  does return after a long idle gap.
- **A missing PDF button is a real answer** — no PDF for that paper, or no access. Report
  it rather than retrying.
- **CNKI supplies the filename** via `Content-Disposition`, often with Chinese
  punctuation. Leave it alone; renaming risks encoding damage for no gain.
- **`get_paper_bibtex(label)`** returns a BibTeX entry for any label, if the user wants
  citations alongside the files.

## 4. Limits — these are not suggestions

- **≤ 20 papers per run.** For more, do a second run after the user reviews the first.
  Never one long unattended loop.
- **One run at a time.** Chromium locks the profile directory; a concurrent run fails.
- **Respect the account's download quota.** CNKI accounts have per-period caps, and a
  batch can exhaust one quickly. If the user has not mentioned their quota, ask.

## 5. Report

Finish with a table — saved (label, title, absolute path, size) and skipped (label, title,
reason) — plus the total count and the absolute save directory so the user can open it.

## On responsible use

Bulk automated downloading is the behaviour most likely to breach CNKI's terms of service
and to get a shared institutional IP range (or your own account) rate-limited. That is why
§4 is written as hard rules rather than as advice — if you fork this, keep them.
