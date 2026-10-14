"""What participants told us: questionnaire answers and conversation transcripts, encrypted at rest.

Kept apart from who the participant is (accounts). Rows are never deleted through a participant:
the foreign keys use PROTECT, so removing a participant with data fails loudly instead of cascading.
"""
