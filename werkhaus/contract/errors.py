"""Errors that cross the API boundary.

Every one of these carries user-facing prose. A Python traceback is never
serialized to a client — it is logged against the request_id and nothing more.
The user is non-technical; "TypeError: NoneType" is not a thing they can act on.
"""

from __future__ import annotations


class WerkhausError(Exception):
    """Base. ``code`` is stable and machine-readable; ``message`` is for humans."""

    code: str = "internal"
    status: int = 500
    message: str = "Something went wrong on our side."
    hint: str | None = None

    def __init__(self, message: str | None = None, *, hint: str | None = None):
        self.message = message or type(self).message
        self.hint = hint if hint is not None else type(self).hint
        super().__init__(self.message)


class NotFound(WerkhausError):
    code = "not_found"
    status = 404
    message = "We couldn't find that."


class CompanyNotFound(NotFound):
    code = "company_not_found"
    message = "That company doesn't exist."


class ShiftNotFound(NotFound):
    code = "shift_not_found"
    message = "That shift doesn't exist."


class ArtifactNotFound(NotFound):
    code = "artifact_not_found"
    message = "That document doesn't exist."


class Conflict(WerkhausError):
    code = "conflict"
    status = 409
    message = "That can't be done right now."


class ShiftAlreadyRunning(Conflict):
    code = "shift_already_running"
    message = "This company is already working."
    hint = "Wait for the current shift to finish, or stop it first."


class TaskAlreadyClaimed(Conflict):
    """Raised by BrainStore's compare-and-set claim. Two roles cannot double-claim."""

    code = "task_already_claimed"
    message = "Someone else already took that task."


class ArtifactOwnedByAnotherRole(Conflict):
    code = "artifact_owned_by_another_role"
    message = "Another employee is working on that document this shift."


class BudgetExceeded(WerkhausError):
    code = "budget_exceeded"
    status = 402
    message = "This company has used its whole budget for now."
    hint = "Raise the cap in Settings to keep going."


class CompanyHalted(Conflict):
    code = "company_halted"
    message = "This company is stopped."
    hint = "Resume it to start another shift."


class PublishBlocked(WerkhausError):
    """The secret scan is a publish gate and it fails closed."""

    code = "publish_blocked"
    status = 422
    message = (
        "We found something private in this company's files, so we didn't publish it."
    )
    hint = "Remove the sensitive value and try again."


class ValidationFailed(WerkhausError):
    code = "invalid_request"
    status = 422
    message = "That request didn't look right."


class OutOfShifts(Conflict):
    """The plan gate. Not an error the user caused — a limit they reached."""

    code = "out_of_shifts"
    message = "You've used the shifts on your plan."
    hint = "More shifts arrive with your next refill."


class EngineNotConfigured(WerkhausError):
    """The server is running, but not with an engine that can do any work.

    Its own class because "the operator forgot an environment variable" and
    "the product is broken" look identical from the front door otherwise.
    """

    code = "engine_not_configured"
    status = 503
    message = "This Werkhaus isn't set up to run companies yet."
    hint = (
        "No employee has a brain to think with yet. Set WERKHAUS_MODEL to a "
        "model string, and the matching provider key, then restart."
    )


class IntegrationNotFound(NotFound):
    code = "integration_not_found"
    message = "We don't know that service."


class IntegrationUnavailable(Conflict):
    code = "integration_unavailable"
    message = "That service isn't available on this plan."


class CredentialRejected(WerkhausError):
    """The value was wrong, or the provider turned it down. Never stored."""

    code = "credential_rejected"
    status = 422
    message = "That didn't work."


class ForbiddenCredential(WerkhausError):
    """One specific key we decline to hold, by name."""

    code = "forbidden_credential"
    status = 422
    message = "That's a master key for your database, and we don't accept those."
    hint = (
        "It can read and change everything, ignoring the rules that protect "
        "your customers' data. Use the access token from your account settings "
        "instead — it's the only one the team needs."
    )
