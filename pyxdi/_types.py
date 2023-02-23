import typing as t

Provider = t.Callable[..., t.Any]
ProviderCallable = t.Callable[..., t.Any]
Scope = t.Literal["transient", "singleton", "request"]
InterfaceT = t.TypeVar("InterfaceT")
ClassT = t.TypeVar("ClassT")
