import os
import pytest

# Ensure tests on Windows Proactor loop do not leave socket connections across closed loops
os.environ["ORCA_DB_POOL"] = "nullpool"
