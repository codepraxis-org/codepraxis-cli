---
description: Save a tested CodePraxis question to the platform and return its link
argument-hint: "<question slug>"
allowed-tools: Read, Bash(codepraxis:*)
---

Ship the question `$1`.

```bash
codepraxis push $1
```

Push saves the question to the platform, and prints its URL. **Put the URL in
your reply**; it is what the author shares.

- **Coding:** the pack goes up with the catalog fields and categories from
  `pack/publish.json`. The solution is kept privately (never in a candidate's
  files) so `pull` can bring it back. The first push writes `challenge_id` into
  `publish.json`; later pushes update that question.
- **Interview:** new or changed files in `entities/` are uploaded, then
  `question.json` is saved. The first push writes its `id` into
  `question.json`; later pushes update it.
- **A draft** keeps one version, updated by each push. **A published
  question** gets a new version on push, and the CLI says so: candidates get it
  from then on. Push never changes whether a question is live.

Categories only apply when the admin account pushes (the public catalog); any
other company's questions stay in that company, with no category.

A draft can be previewed, but not assigned or added to a template. The author
makes it public from the question's page on the website. Say that in one line
with the URL.

If a container is still open for the question, `codepraxis stop $1` hands it
back now; otherwise it is reclaimed after 30 idle minutes.
