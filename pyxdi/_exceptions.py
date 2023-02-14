class BindingDoesNotExist(Exception):
    pass


class ProviderAlreadyBound(Exception):
    pass


class InvalidMode(ValueError):
    pass


class InvalidProviderType(Exception):
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
