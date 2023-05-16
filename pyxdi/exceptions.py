class PyxDIError(Exception):
    pass


class ProviderError(PyxDIError):
    pass


class InvalidScope(PyxDIError):
    pass


class ScopeMismatch(PyxDIError):
    pass


class AnnotationError(PyxDIError):
    pass


class UnknownDependency(PyxDIError):
    pass
