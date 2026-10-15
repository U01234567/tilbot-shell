"""The researcher dashboard: how the study is going, and the data export.

Reached only through the researcher port (8081, this computer only), never through the public site.
Every page needs a researcher login: Django's own user accounts, made with python start_shell.py researcher,
which also makes a Tilbot account with the same name and password (management/commands/researcher.py).
Later: status per component, recent log lines, CPU and memory.
"""
