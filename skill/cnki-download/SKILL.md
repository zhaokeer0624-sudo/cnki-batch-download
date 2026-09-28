---
name: cnki-download
description: >-
  Download a specific paper's PDF from CNKI (中国知网) through the cnki-mcp MCP
  server, navigating its path, label and verification quirks. Use when the user
  asks to fetch or save a CNKI paper PDF — "download this paper", "把这篇知网论文下载下来",
  "save this PDF to ..." — or when they give a CNKI title/链接 and want the file
  on disk. One paper per request; this skill does not do bulk downloads.
---

# Download one CNKI paper as PDF

Uses the `cnki-mcp` MCP server. Both this skill and that server assume:

- `cnki-mcp` is installed **and patched** — the patch is required, because
  unpatched `cnki-mcp` times out on every article page. See the parent
  repository's `patch_cnki_mcp.py`.
- Your CNKI account carries access to the paper. The patch grants no access.

## Steps

1. **Get a label.** Downloads are addressed by the short `label` that
   `search_cnki` returns — **not by URL**. So:
   - title only → `find_best_match(title)` then confirm it is the right paper
   - topic/keyword → `search_cnki(query, ...)` and pick from `papers[].label`
   - already have a label from an earlier search in this session → use it

2. **Download it.**

   ```
   download_paper_pdf(paper=<label>, save_dir=<absolute path>)
   ```

   `save_dir` must be an **absolute path**. The call creates the directory.

3. **Verify the file.** On success the result has `file_path`. Confirm the bytes
   actually are a PDF before reporting success:

   ```bash
   head -c 5 "<file_path>"   # must print %PDF-
   ```

   A file that is missing, empty, or starts with `<` is an HTML error page, not
   a paper.

## Pitfalls that actually bite

- **Save directory must be writable.** On Windows, creating a folder directly in
  a drive root (`D:\papers`) fails with `PermissionError: [WinError 5]`. Use a
  path inside an existing folder, e.g. `D:\Research\papers`.
- **The first run blocks on a captcha by design.** A visible Chromium window
  opens and CNKI shows a slider. Wait for the user to slide it — do not treat the
  pause as a hang and do not retry. The session persists, so this is rare rather
  than per-call — but it does return after a long idle gap.
- **A missing PDF button is a real answer.** The server reports "PDF下载按钮未找到"
  when the paper has no PDF, or when your account has no access to it. Report that
  as the outcome rather than retrying.
- **CNKI supplies the filename**, via `Content-Disposition`, and it often contains
  Chinese punctuation. Leave it alone; renaming risks encoding damage for no gain.
- **`get_paper_bibtex(label)`** returns a BibTeX entry for the same label if the
  user wants the citation alongside the file.

## Scope

This skill handles **one paper per request**. For many papers at once — sorting by
citation count, filtering by journal or year, saving the top N — use the sibling
`cnki-batch-download` skill, which adds the batch loop together with the rate limits and
per-run caps that keep it safe to use.
