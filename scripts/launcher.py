"""Entry script for frozen builds (PyInstaller needs a file, not a module)."""
from gantry.app import main

raise SystemExit(main())
