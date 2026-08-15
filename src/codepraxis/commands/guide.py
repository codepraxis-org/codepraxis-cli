"""``codepraxis guide`` — the whole thing explained once.

Deliberately short. Two things are kept out on purpose:

- the ``testCases`` contract and the pack layout, because an author using the
  plugin never writes either by hand, and putting them in front of a new
  company makes the job look harder than it is;
- ``review``, because it runs inside ``build`` and naming it in user-facing
  copy makes authors think they are responsible for invoking it.

What is left is only what the company itself decides.
"""

from __future__ import annotations

EXIT_OK = 0

GUIDE = """\
codepraxis — build real-world coding assessments

  WHAT A QUESTION IS

    A folder. The candidate gets the starting code.
    A grader runs tests they cannot see.

    You describe what you want tested. Claude writes the
    code, the tests, and a working solution, then checks
    its own work before you ever see it.

  THE STEPS

    plan      talk it through, find real code, agree what to test
    approve   accept the plan — nothing is built until you do
    build     Claude writes and tests the question
    ship      publish as a draft, then go live

    Any time you like:

    find-repos  find a repository worth building a question from
    try         open it exactly as a candidate would
    evaluate    is it any good, and can a model beat it
    edit        change one later

    Run `codepraxis` any time to see where you are.

    Planning writes a plan and stops. Read it, then:

        codepraxis approve my-question

  WORKING WITH CLAUDE CODE

    The steps above are driven by Claude. Run these two once,
    in Claude Code — the same on every machine:

        /plugin marketplace add codepraxis-org/codepraxis-cli
        /plugin install codepraxis@codepraxis

    Then you get:

        /codepraxis:plan      design a question, no code yet
        /codepraxis:build     write it, test it, fix it
        /codepraxis:ship      publish as a draft

        /codepraxis:try       open it as a candidate would
        /codepraxis:evaluate  is it good, can a model beat it
        /codepraxis:edit      change an existing one

    Without the plugin the CLI still works on its own:
    `codepraxis find-repos`, `new`, `validate`, `ship`, `list`,
    `edit`.

    Working offline, or editing the prompts yourself? Then
    `codepraxis install claude-plugin` writes a local copy.

  WHAT MAKES A GOOD QUESTION

    Start from a real repository.  A model has never seen your
    code, so a question built on it cannot be answered from the
    brief alone. `codepraxis find-repos` will find one if you
    cannot share yours. Puzzles tell you who practices puzzles.

    Give them something to start from.  A blank file wastes
    the first fifteen minutes on setup, not thinking.

    Make sure AI cannot shortcut it.  Candidates have a model
    in the container, so we measure it rather than guess: a
    fresh model attempts your question from the brief alone and
    we report how far it got. Fewer cases passed is better.

    Sit the question yourself.  Ten minutes in `try` finds
    more problems than any amount of reviewing.

  SEE IT FIRST

    codepraxis example        open a real question, no account needed
"""


def run() -> int:
    print(GUIDE, end="")
    return EXIT_OK
