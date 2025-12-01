# Scopes

`AnyDI` supports three built-in scopes for providers:

* `transient` - New instance every time
* `singleton` - One instance for the entire application
* `request` - One instance per request context

In addition to these built-in scopes, you can register custom scopes to fit your application's specific needs.

## `transient` scope

Providers with transient scope create a new instance of the object each time it's requested. You can set the scope when registering a provider.

### Example

```python
import uuid

from anydi import Container


class RequestTracker:
    def __init__(self) -> None:
        self.request_id = str(uuid.uuid4())


container = Container()


@container.provider(scope="transient")
def request_tracker() -> RequestTracker:
    return RequestTracker()


# Each resolve creates a new instance with a different request ID
tracker1 = container.resolve(RequestTracker)
tracker2 = container.resolve(RequestTracker)

assert tracker1.request_id != tracker2.request_id
```

## `singleton` scope

Providers with singleton scope create a single instance of the object and return it every time it's requested.

### Example

```python
from anydi import Container


class Service:
    def __init__(self, name: str) -> None:
        self.name = name


container = Container()


@container.provider(scope="singleton")
def service() -> Service:
    return Service(name="demo")


assert container.resolve(Service) == container.resolve(Service)
```

## `request` scope

Providers with request scope create an instance of the object for each request. The instance is only available within the context of the request.

### Example

```python
from anydi import Container


class Request:
    def __init__(self, path: str) -> None:
        self.path = path


container = Container()


@container.provider(scope="request")
def request_provider() -> Request:
    return Request(path="/")


with container.request_context():
    assert container.resolve(Request).path == "/"

container.resolve(Request)  # this will raise LookupError
```

or using asynchronous request context:

```python
from anydi import Container

container = Container()


@container.provider(scope="request")
def request_provider() -> Request:
    return Request(path="/")


async def main() -> None:
    async with container.arequest_context():
        assert (await container.aresolve(Request).path) == "/"
```

## `request` scoped instances

In `AnyDI`, you can create `request-scoped` instances to manage dependencies that should be instantiated per request.
This is particularly useful when handling dependencies with request-specific data that need to be isolated across different requests.

To create a request context, you use the `request_context` (or `arequest_context` for async) method on the container.
This context is then used to resolve dependencies scoped to the current request.

```python
from typing import Annotated

from anydi import Container


class UserContext:
    def __init__(self, user_id: str, tenant_id: str) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id


container = Container()


@container.provider(scope="request")
def user_context(request: Request) -> Annotated[UserContext, "current_user"]:
    return UserContext(user_id=request.param, tenant_id="tenant-1")


with container.request_context() as ctx:
    ctx.set(Request, Request(param="user-456"))

    user = container.resolve(Annotated[UserContext, "current_user"])
    assert user.user_id == "user-456"
    assert user.tenant_id == "tenant-1"
```

## Custom Scopes

In addition to the built-in scopes, `AnyDI` allows you to define custom scopes for your application. Custom scopes are useful when you need to manage the lifecycle of dependencies beyond the standard singleton, transient, and request scopes.

### Registering Custom Scopes

To register a custom scope, use the `register_scope` method on the container:

```python
from anydi import Container

container = Container()

# Register a custom scope without parent scopes
container.register_scope("task")

# Register a custom scope with parent scopes
container.register_scope("workflow", parents=["task"])
```

### Scope Hierarchy

Custom scopes support parent-child relationships. A scope can only depend on:
- Itself
- `singleton` scope (always allowed)
- Its parent scopes

For example, if you have a hierarchy like: `workflow` → `task` → `singleton`, then:

- `workflow` scoped providers can depend on `workflow`, `task`, and `singleton` scopes
- `task` scoped providers can depend on `task` and `singleton` scopes
- `singleton` scoped providers can only depend on `singleton` scope
- `transient` scoped providers can depend on any scope

### Using Custom Scopes

Once registered, custom scopes work just like the built-in `request` scope:

```python
from anydi import Container


class TaskContext:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id


class WorkflowEngine:
    def __init__(self, task_context: TaskContext) -> None:
        self.task_context = task_context


container = Container()

# Register custom scopes
container.register_scope("task")
container.register_scope("workflow", parents=["task"])

# Register providers with custom scopes
@container.provider(scope="task")  # type: ignore[arg-type]
def task_context() -> TaskContext:
    return TaskContext(task_id="task-123")


@container.provider(scope="workflow")  # type: ignore[arg-type]
def workflow_engine(task_context: TaskContext) -> WorkflowEngine:
    return WorkflowEngine(task_context)


# Use custom scoped context
with container.scoped_context("task"):
    with container.scoped_context("workflow"):
        engine = container.resolve(WorkflowEngine)
        assert engine.task_context.task_id == "task-123"
```

### Async Custom Scopes

Custom scopes also support async contexts:

```python
async def process_workflow() -> None:
    async with container.ascoped_context("task"):
        async with container.ascoped_context("workflow"):
            engine = await container.aresolve(WorkflowEngine)
            # Process workflow...
```

### Best Practices

1. **Define clear hierarchies**: Structure your scopes to reflect your application's logical boundaries (e.g., `request` → `transaction` → `batch`)
2. **Avoid deep nesting**: Keep scope hierarchies shallow for better performance and maintainability
3. **Use meaningful names**: Choose scope names that clearly indicate their purpose (`task`, `session`, `tenant`, etc.)
4. **Validate dependencies**: The container automatically validates that scoped dependencies follow the hierarchy rules

### Common Use Cases

#### Multi-tenancy
```python
container.register_scope("tenant")

@container.provider(scope="tenant")  # type: ignore[arg-type]
def tenant_db() -> TenantDatabase:
    return TenantDatabase()
```

#### Background jobs
```python
container.register_scope("job")

@container.provider(scope="job")  # type: ignore[arg-type]
def job_context() -> JobContext:
    return JobContext()
```

#### User sessions
```python
container.register_scope("session")

@container.provider(scope="session")  # type: ignore[arg-type]
def session_data() -> SessionData:
    return SessionData()
```

