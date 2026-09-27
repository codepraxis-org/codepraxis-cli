# How making a question works

## The two pieces

- **The plugin** — five things you type in Claude Code. It tells the AI how
  to think about authoring a question.
- **The CLI** — a small command-line tool the plugin calls behind the scenes.
  You rarely type these yourself.

## What you type, in order

| You type | What happens | You get |
|---|---|---|
| `/codepraxis:plan` | Talk it through with the AI: what to test, whether you have a repo. It writes one file, the plan. | a written plan |
| `/codepraxis:build` | The AI writes the actual question: the brief, the starting code, the tests, the reference solution. It checks its own work as it goes, silently, until it's solid. | a working question |
| `/codepraxis:try` | Publishes it as a draft and hands you a link. | a link you can open and try yourself |
| `/codepraxis:ship` | Runs one final check, then publishes. Asks you separately before making it live to candidates. | a live question |
| `/codepraxis:edit` | Change something already shipped, and republish it as a new version (not a duplicate). | an updated question |

That's it — four steps for a new question, plus edit for changing one later.
No approval step in between, no separate "evaluate" step, nothing you have to
run by hand to check the work — the checking happens on its own, inside build
and again inside ship.

## What changed from before

- **Approval step — removed.** There used to be a manual on/off switch
  (`codepraxis approve`) between plan and build. Gone. Plan flows straight
  into build.
- **Evaluate — removed as its own step.** It used to be something you ran
  separately to judge whether a question was any good. That check now
  happens automatically, folded into ship, right before publishing.
- **Validate — removed as something you type.** The check itself (does the
  reference solution pass, does the untouched starting code fail) still runs
  — build uses it in its own loop while writing the question, and ship runs
  it once more before publishing. You just never type the word yourself.
- **Try — now just means "ship a draft."** Ship already hands back a working
  link even for a draft, so try is that, by another name.
- **Login — removed.** No separate login step. The tool reads your API key
  from your environment; if it's missing, it tells you exactly what to set.
- **Find a repo to build from — removed.** The AI does this itself in
  conversation during plan. No separate command for it.

## The CLI commands that remain

Nine, down from thirteen. Only four of these are things you'd type by hand
day to day — the rest are one-off setup or used internally by the plugin.

| Command | Used how |
|---|---|
| `ship` | by hand — publish (draft or live) |
| `edit` | by hand — change something already shipped |
| `list` | by hand — see your questions |
| `delete` | by hand — remove one |
| `lint` | occasional — a quick structural check |
| `install` | once — set up the plugin |
| `example` | occasional — see a sample question |
| `guide` | occasional — reminder of what to do next |
| `new` | never by hand — build calls this internally to create empty starter files |

## What a question should look like now

Not a single "write this function" prompt. The default shape is:

1. **Understand** — the candidate reads and makes sense of a real piece of
   architecture.
2. **Decide** — they make a design choice and can defend it.
3. **Implement** — they build it.

This matters because candidates have AI in the container. A single-shot
question is something a model answers instantly and tells you nothing. The
report also shows exactly how AI was used — the prompts, the chat, the
terminal history — so a good question is one where that visible trail
actually tells you something: did they understand what they asked for, or
did they just accept whatever came back.
