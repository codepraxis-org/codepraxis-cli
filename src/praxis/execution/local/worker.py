"""Subprocess entry point that loads and runs a pack's ``testCases``.

Runs in its own interpreter for two reasons the runner does not have to care
about: pack test code is untrusted and may call ``sys.exit`` or corrupt module
state, and the CLI is a long-lived tool that must survive it.

Within the subprocess the execution is faithful to ``koro/test_runner.py``: the
cases run in-process so ``self.msg`` is readable afterwards, which is what
decides pass/fail.

Deliberately standalone — it imports nothing from ``praxis`` so it can be
executed by any interpreter, including one where the CLI is not installed.

Protocol: ``python worker.py <config.json> <results.json>``. Results are written
to a file rather than stdout because pack tests print freely to stdout.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import re
import signal
import sys
import time
import traceback

PASS_SENTINEL = "PASS"
BAD_INPUT_SENTINEL = "._bad_input"
TEST_CASE_PREFIX = "test_case"
TEST_CLASS_NAME = "testCases"
ORDER_PATTERN = re.compile(r"\d+")


class _Timeout(Exception):
    pass


def _load_module(test_file, injected_names):
    """Import the test module, injecting the names the runner provides.

    ``koro/test_loader.py`` sets ``execute_bin`` on the module before
    instantiation; EMB/LNX additionally get ``cmd``. Tests may reference these
    at module scope, so they must exist before ``exec_module`` runs.
    """
    spec = importlib.util.spec_from_file_location("praxis_test_module", test_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load a Python module from {test_file}")
    module = importlib.util.module_from_spec(spec)

    def _unavailable(*_args, **_kwargs):
        raise RuntimeError(
            "This pack calls a runner-injected helper that the local harness does not "
            "emulate. Run `praxis validate --remote` to exercise it."
        )

    for name in injected_names:
        setattr(module, name, _unavailable)

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _discover(instance):
    """Collect and order ``test_case_*`` methods exactly as koro does.

    Ordering key is the first run of digits anywhere in the name, which is why
    zero-padded names are ambiguous.
    """
    methods = []
    for name, func in inspect.getmembers(instance, predicate=inspect.ismethod):
        if not name.startswith(TEST_CASE_PREFIX):
            continue
        signature = inspect.signature(func)
        timeout_param = signature.parameters.get("timeout_window")
        override_param = signature.parameters.get("override")
        methods.append(
            {
                "name": name,
                "func": func,
                "timeout_window": None if timeout_param is None else timeout_param.default,
                "override": None if override_param is None else override_param.default,
            }
        )

    def _key(entry):
        found = ORDER_PATTERN.search(entry["name"])
        return int(found.group()) if found else 0

    methods.sort(key=_key)
    return methods


def _run_case(instance, entry, default_timeout_ms):
    """Execute one case with koro's override-1 semantics."""
    timeout_ms = entry["timeout_window"] or default_timeout_ms or 0
    timeout_secs = float(timeout_ms) / 1000.0

    instance.msg = ""

    result = None
    error = None
    timed_out = False
    can_alarm = hasattr(signal, "SIGALRM")

    previous = signal.getsignal(signal.SIGALRM) if can_alarm else None
    started = time.time() * 1000
    try:
        if can_alarm and timeout_secs > 0:

            def _handler(_signum, _frame):
                raise _Timeout()

            signal.signal(signal.SIGALRM, _handler)
            signal.setitimer(signal.ITIMER_REAL, timeout_secs)
        result = entry["func"]()
    except _Timeout:
        timed_out = True
    except Exception:  # noqa: BLE001 - a failing test must not kill the harness
        error = traceback.format_exc(limit=6)
    finally:
        if can_alarm:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous if previous else signal.SIG_DFL)
    elapsed = (time.time() * 1000) - started

    if timed_out:
        return {
            "name": entry["name"],
            "status": "timeout",
            "expected": "N/A",
            "output": f"Timed out after {timeout_ms} ms",
            "duration_ms": elapsed,
        }

    if error is not None:
        return {
            "name": entry["name"],
            "status": "error",
            "expected": "N/A",
            "output": f"Test execution error: {error}",
            "duration_ms": elapsed,
        }

    rendered = "" if result is None else str(result)
    if BAD_INPUT_SENTINEL in rendered:
        return {
            "name": entry["name"],
            "status": "fail",
            "expected": "N/A",
            "output": "Bad input",
            "duration_ms": elapsed,
        }

    expected = "N/A"
    success_message = "N/A"
    if isinstance(result, tuple) and len(result) >= 2:
        expected = str(result[0])
        success_message = str(result[1])
    elif result is not None:
        expected = str(result)

    msg = str(getattr(instance, "msg", "") or "")
    passed = msg == PASS_SENTINEL

    return {
        "name": entry["name"],
        "status": "pass" if passed else "fail",
        "expected": expected,
        "output": success_message if passed else (msg or "Test failed"),
        "duration_ms": elapsed,
    }


def main(argv):
    if len(argv) != 3:
        print("usage: worker.py <config.json> <results.json>", file=sys.stderr)
        return 2

    with open(argv[1], "r", encoding="utf-8") as handle:
        config = json.load(handle)
    output_path = argv[2]

    payload = {"cases": [], "attributes": {}, "fatal": None}

    try:
        module = _load_module(config["test_file"], config.get("injected_names", []))
        test_class = getattr(module, TEST_CLASS_NAME, None)
        if test_class is None:
            raise AttributeError(
                f"No {TEST_CLASS_NAME!r} class found in {config['test_file']}. "
                f"The runner looks for exactly this name."
            )

        # koro instantiates with a single argument: the workspace path.
        instance = test_class(config["workspace"])

        run_count = getattr(instance, "RUN", None)
        run_case_inputs = getattr(instance, "RunCaseInputs", None)
        payload["attributes"] = {
            "RUN": run_count,
            "RunCaseInputs": list(run_case_inputs) if isinstance(run_case_inputs, (list, tuple)) else None,
            "exe": getattr(instance, "exe", None),
            "default_timeout_window": getattr(instance, "default_timeout_window", None),
            "present": [name for name in config.get("expected_attrs", []) if hasattr(instance, name)],
        }

        entries = _discover(instance)
        payload["attributes"]["discovered"] = [entry["name"] for entry in entries]

        default_timeout = getattr(instance, "default_timeout_window", 0) or 0
        limit = config.get("limit")
        selected = entries if limit is None else entries[:limit]

        for index, entry in enumerate(selected):
            case = _run_case(instance, entry, default_timeout)
            case["hidden"] = bool(run_count) and index >= int(run_count)
            case["override"] = entry["override"]
            payload["cases"].append(case)

    except BaseException:  # noqa: BLE001 - report, never crash the parent
        payload["fatal"] = traceback.format_exc(limit=8)

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
