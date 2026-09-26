---
description: Save a tested CodePraxis question as a draft and return its link
argument-hint: "<question slug>"
allowed-tools: Read, Bash(codepraxis:*)
---

Ship the question `$1`.

```bash
codepraxis publish $1
```

- **Coding:** uploads the pack with the catalog fields and categories from
  `pack/publish.json`. The platform stores it without the solution. The first
  publish creates the question and writes its `challenge_id` into
  `publish.json`; later publishes are new versions of it.
- **Interview:** uploads the files in `entities/` that changed, then saves
  `question.json`. The first save writes the question's `id` into
  `question.json`; later saves update it.

It prints the question's URL. **Put the URL in your reply**; it is what the
author shares.

Categories only apply when the admin account publishes (the public catalog);
any other company's questions stay in that company, with no category.

The question is always saved as a **draft**. A draft can be previewed, but not
assigned or added to a template. The author makes it public from the
question's page on the website. Say that in one line with the URL.

If a container is still open for the question, `codepraxis stop $1` hands it
back now; otherwise it is reclaimed after 30 idle minutes.
