"""__TITLE__"""

import sys


def total(numbers):
    """Return the sum of ``numbers``."""
    raise NotImplementedError("implement total()")


if __name__ == "__main__":
    print(total([int(argument) for argument in sys.argv[1:]]))
