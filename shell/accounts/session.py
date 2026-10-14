"""Which participant this browser belongs to, kept in the Django session."""

SESSION_KEY = "participant_id"


def sign_in_as(request, participant) -> None:
    request.session.cycle_key()  # a fresh session id on sign-in prevents session fixation
    request.session[SESSION_KEY] = participant.pk


def signed_in_id(request) -> int | None:
    return request.session.get(SESSION_KEY)
