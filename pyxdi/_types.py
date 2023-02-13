import typing as t

Provider = t.Callable[..., t.Any]
ProviderFunctionT = t.TypeVar("ProviderFunctionT", bound=t.Callable[..., t.Any])
Scope = t.Literal["transient", "singleton", "request"]
Mode = t.Literal["sync", "async"]
InterfaceT = t.TypeVar("InterfaceT")
