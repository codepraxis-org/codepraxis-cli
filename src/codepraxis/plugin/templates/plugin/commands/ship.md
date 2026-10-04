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
- **MCQ bank:** the same checks as `test` run first, and stop the push on any
  error. New or changed images in `images/` are uploaded, then the bank is saved.
  **A push replaces the whole bank** (name, description, category, every
  question); candidates' past attempts keep their own copy. The first push keeps
  the bank id in `.codepraxis.json`; later pushes replace that bank. If the
  platform refuses it, every problem is listed: fix them all and push again. A
  bank has no draft: it is usable as soon as it is pushed. Put the printed link
  and the count per difficulty in your reply, and say it is used by adding it to a
  template's Knowledge check round.
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
