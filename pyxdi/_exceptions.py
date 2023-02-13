class BindError(RuntimeError):
    pass


class ProviderAlreadyBound(BindError):
    pass


class InvalidMode(BindError):
    pass


class InvalidScope(BindError):
    pass


class ScopeMismatch(BindError):
    pass
