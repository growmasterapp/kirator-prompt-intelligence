class KiratorError(Exception):
    """Base exception for Kirator Prompt Intelligence."""


class RouterError(KiratorError):
    pass


class ModelError(KiratorError):
    pass


class PipelineError(KiratorError):
    pass


class PipelineCancelled(KiratorError):
    """Raised when a running pipeline is cancelled by the user."""


def reraise_if_cancelled(exc: BaseException) -> None:
    """
    Let a user cancel escape a stage's "keep going" error handler.

    Several stages catch Exception and return a fallback so one bad model
    reply does not kill the run. Cancel must not be treated as a bad reply.
    """
    if isinstance(exc, PipelineCancelled):
        raise exc
