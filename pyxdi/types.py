import typing as t

ProviderObj = t.Callable[..., t.Any]
Scope = t.Literal["transient", "singleton", "request"]
InterfaceT = t.TypeVar("InterfaceT")
