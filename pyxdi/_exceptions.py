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


class MissingProviderAnnotation(Exception):
    pass


class UnknownProviderDependency(Exception):
    pass
