class ProviderError(Exception):
    pass


class InvalidScope(Exception):
    pass


class ScopeMismatch(Exception):
    pass


class MissingAnnotation(Exception):
    pass


class NotSupportedAnnotation(Exception):
    pass


class UnknownDependency(Exception):
    pass
