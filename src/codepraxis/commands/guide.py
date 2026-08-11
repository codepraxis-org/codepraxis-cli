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

    plan      talk it through, agree what to test
    approve   accept the plan — nothing is built until you do
    build     Claude writes and tests the question
    try       open it exactly as a candidate would
    ship      publish as a draft, then go live
    edit      change one later

    Run `codepraxis` any time to see where you are.

    Planning writes a plan and stops. Read it, then:

        codepraxis approve my-question

  WORKING WITH CLAUDE CODE

    The steps above are driven by Claude. Run these two once,
    in Claude Code — the same on every machine:

        /plugin marketplace add codepraxis-org/codepraxis-cli
        /plugin install codepraxis@codepraxis

    Then you get:

        /codepraxis:plan    design a question, no code yet
        /codepraxis:build   write it, test it, fix it
        /codepraxis:try     open it as a candidate would
        /codepraxis:ship    publish as a draft
        /codepraxis:edit    change an existing one

    Without the plugin the CLI still works on its own:
    `codepraxis new`, `validate`, `ship`, `list`, `edit`.

    Working offline, or editing the prompts yourself? Then
    `codepraxis install claude-plugin` writes a local copy.

  WHAT MAKES A GOOD QUESTION

    Use real work.  A bug you actually shipped, a service you
    actually run. Puzzles tell you who practices puzzles.

    Give them something to start from.  A blank file wastes
    the first fifteen minutes on setup, not thinking.

    Make sure AI cannot shortcut it.  Candidates have a model
    in the container. We check this while planning and will
    stop you if the question is one prompt away from done.

    Sit the question yourself.  Ten minutes in `try` finds
    more problems than any amount of reviewing.

  SEE IT FIRST

    codepraxis example        open a real question, no account needed
"""


def run() -> int:
    print(GUIDE, end="")
    return EXIT_OK
