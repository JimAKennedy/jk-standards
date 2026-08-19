"""Enable ``python -m jk_standards`` as an alias for the ``jk-standards`` CLI.

The console-script entry point (``jk-standards = jk_standards.cli:main``) is the
primary way to run the checks, but ``python -m jk_standards <args>`` is the form
that does not depend on the script being on ``PATH`` — it works from any
interpreter that can import the package. Both dispatch to the same ``cli.main``.
"""

from __future__ import annotations

import sys

from jk_standards.cli import main

if __name__ == "__main__":
    sys.exit(main())
