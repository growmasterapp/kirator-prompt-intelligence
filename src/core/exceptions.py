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
