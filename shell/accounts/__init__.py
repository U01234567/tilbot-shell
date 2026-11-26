"""Accounts: sign up, sign in and sign out with a participant code.

Participants are not Django users. They have a random 4-character code, an age and a gender,
and the browser session remembers which participant is signed in (accounts/session.py).
A study can sign participants in by the ID in the link instead (project.toml's [signup] by_link).
"""
