class VesperError(Exception):
    """Base exception for all Vesper errors."""
    pass

class InvalidAgentSpecError(VesperError):
    """Raised when a YAML manifest fails validation against Pydantic schemas."""
    pass

class InvalidModelNameError(VesperError):
    """Raised when a model string is not supported by the Vesper engine."""
    pass

class NoChangeDetectedError(VesperError):
    """Raised when an applied manifest matches the active state exactly."""
    pass

class ResourceNameNotFoundError(VesperError):
    """Raised when a resource name is not found."""
    pass

class ResourceVersionNotFoundError(VesperError):
    """Raised when a resource version is not found."""
    
class ModelNotSupportedError(VesperError):
    """Raised when an unknown model name is requested."""
    pass

class BudgetExceededError(VesperError):
    """Raised when a run exceeds its allocated maxCostPerRun."""
    pass

class LLMProviderError(VesperError):
    """Raised when an external LLM API call fails."""
    pass

class ToolNotFoundError(VesperError):
    """Raised when a tool listed in manifest is not found."""
    pass
