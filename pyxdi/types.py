import typing as t

ProviderCallable = t.Callable[..., t.Any]
Scope = t.Literal["transient", "singleton", "request"]
InterfaceT = t.TypeVar("InterfaceT")
ClassT = t.TypeVar("ClassT")
