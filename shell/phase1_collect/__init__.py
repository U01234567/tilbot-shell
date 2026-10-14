"""Phase 1, collect data: what happens after each questionnaire answer.

The questions are written in Tilbot's studio. After each one, a Processing block "save" sends
the answer to /bridge/save with its item id. The rules here decide, from questionnaire.toml,
whether the answer is valid and whether follow-up questions come next. Pure functions only:
the bridge does the saving.
"""
