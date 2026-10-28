import sys

from core.cli import main

# Umlauts must print on a Windows console too.
sys.stdout.reconfigure(encoding="utf-8")
main()
