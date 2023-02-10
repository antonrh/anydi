import typing as t

Dependency = t.Callable[..., t.Any]
DependencyFunctionT = t.TypeVar("DependencyFunctionT", bound=t.Callable[..., t.Any])
Scope = t.Literal["transient", "singleton", "request"]
Mode = t.Literal["sync", "async"]
InterfaceT = t.TypeVar("InterfaceT")
