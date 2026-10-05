---
description: Build a whole assessment (a draft template) from a job description
argument-hint: "<which position are you hiring for?>"
allowed-tools: Read, Glob, Grep, Write, Edit, Bash(codepraxis:*)
---

Build an assessment for: **$ARGUMENTS**

Read the `assessment-from-jd` skill now, and its `output.md`. Follow it step by
step. You write `templates/<slug>/PLAN.md` and `templates/<slug>/template.json`,
and save the template as a **draft**. You never publish anything.

## 1. Get the basics

Ask for these together, in one message. Skip any the conversation already
answers.

1. **Job description.** Ask them to paste it.
2. **Time budget.** Minutes for the whole assessment (default 90 to 120).
3. **AI assistant.** Whether candidates get the AI agent.

## 2. Plan from the library

```bash
codepraxis library --json
```

Map each must-have skill in the JD to one round and one question, as the skill
says. Prefer published platform questions. Write PLAN.md, show it to the author
with the minutes per round and the total, and let them change it before you go
on.

## 3. Fill the gaps

For each must-have no question covers, plan and build a new question with the
skill for its kind (`question-coding`, `question-coding-ai`, `question-interview`,
`question-mcq`), the way `/codepraxis:plan` and `/codepraxis:build` do, and push it:
it is saved as a draft. Reference it in `template.json` by its folder.

## 4. Test and save

```bash
codepraxis test <slug>
codepraxis push <slug>
```

`test` resolves every question, checks it is in the library, prints the minutes
per round and the total, and lists the questions still in draft. Fix every `✗`
and test again. `push` saves the template as a draft and prints its link.

## 5. Hand off

Put the link in your reply, with the total minutes and the questions still in
draft. Then, in one line each: review the template in the dashboard, publish its
draft questions, then publish the template.
