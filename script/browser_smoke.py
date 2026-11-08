"""Compatibility entry point for the full English-default browser acceptance."""

import os

os.environ.setdefault("ROBODATAOPS_QA_URL", "http://127.0.0.1:8501")

from browser_v1 import main  # noqa: E402

if __name__ == "__main__":
    main()
