"""__TITLE__ — reference solution."""

import sys


def total(numbers):
    """Return the sum of ``numbers``."""
    return sum(numbers)


if __name__ == "__main__":
    print(total([int(argument) for argument in sys.argv[1:]]))
