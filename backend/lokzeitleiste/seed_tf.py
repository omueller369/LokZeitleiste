"""Compatibility entry point for the complete fictional TF reset."""
from .accounts.seed_demo_tf import main, replace_all_tf


def replace_tf(db, today):
    return replace_all_tf(db, today=today)


if __name__ == '__main__':
    main()
