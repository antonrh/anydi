class PyxDIError(Exception):
    pass


class ProviderError(PyxDIError):
    pass


class InvalidScopeError(PyxDIError):
    pass


class ScopeMismatchError(PyxDIError):
    pass


class AnnotationError(PyxDIError):
    pass


class UnknownDependencyError(PyxDIError):
    pass
