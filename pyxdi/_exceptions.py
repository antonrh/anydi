class ProviderNotRegistered(Exception):
    pass


class ProviderNotStarted(Exception):
    pass


class BindingDoesNotExist(Exception):
    pass


class ProviderAlreadyRegistered(Exception):
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
