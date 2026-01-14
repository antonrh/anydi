# Scopes

`AnyDI` has three built-in scopes:

* `transient` - Creates new instance every time
* `singleton` - Creates one instance for entire application
* `request` - Creates one instance per request context

You can also create custom scopes for your specific needs.

## `transient` scope

Transient providers create a new instance every time you request it.

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

Singleton providers create one instance and return the same instance every time.

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

Request providers create one instance for each request. You can only use the instance inside the request context.

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

You can create request-scoped instances for dependencies that need to be created per request. This is useful when you have request-specific data that should be separate for each request.

To create a request context, use the `request_context` method (or `arequest_context` for async). Then you can resolve dependencies for that request.

### Using `FromContext` for external dependencies

When a scoped provider depends on a value that will be provided at runtime via `context.set()`, use the `FromContext` marker to explicitly declare this dependency:

```python
from typing import Annotated

from anydi import Container, FromContext


class Request:
    def __init__(self, param: str) -> None:
        self.param = param


class UserContext:
    def __init__(self, user_id: str, tenant_id: str) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id


container = Container()


@container.provider(scope="request")
def user_context(request: FromContext[Request]) -> Annotated[UserContext, "current_user"]:
    return UserContext(user_id=request.param, tenant_id="tenant-1")


with container.request_context() as ctx:
    ctx.set(Request, Request(param="user-456"))

    user = container.resolve(Annotated[UserContext, "current_user"])
    assert user.user_id == "user-456"
    assert user.tenant_id == "tenant-1"
```

The `FromContext[T]` marker tells AnyDI that:

1. The `Request` type will be provided via `context.set()` at runtime
2. The provider should wait for this value from the scoped context
3. A `LookupError` will be raised if the value is not set before resolution

This makes the dependency explicit and type-safe. Without `FromContext`, unregistered dependencies will raise an error at provider registration time.

## Custom Scopes

You can create custom scopes for your application. Custom scopes are useful when you need to manage dependencies differently from the standard scopes.

### How to register custom scopes

Use the `register_scope` method:

```python
from anydi import Container

container = Container()

# Register a custom scope without parent scopes
container.register_scope("task")

# Register a custom scope with parent scopes
container.register_scope("workflow", parents=["task"])
```

### Scope hierarchy

Custom scopes can have parent-child relationships. A scope can only use dependencies from:
- Itself
- `singleton` scope (always allowed)
- Its parent scopes

For example, if you have: `workflow` → `task` → `singleton`, then:

- `workflow` providers can use `workflow`, `task`, and `singleton` dependencies
- `task` providers can use `task` and `singleton` dependencies
- `singleton` providers can only use `singleton` dependencies
- `transient` providers can use any dependencies

### How to use custom scopes

Custom scopes work like the built-in `request` scope:

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
@container.provider(scope="task")
def task_context() -> TaskContext:
    return TaskContext(task_id="task-123")


@container.provider(scope="workflow")
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

### Best practices

1. **Clear hierarchies**: Structure scopes to match your application logic (e.g., `request` → `transaction` → `batch`)
2. **Avoid deep nesting**: Keep hierarchies simple for better performance
3. **Use clear names**: Choose names that show the scope purpose (`task`, `session`, `tenant`, etc.)
4. **Validate dependencies**: Container automatically checks that dependencies follow the hierarchy rules

### Common Use Cases

#### Multi-tenancy
```python
container.register_scope("tenant")

@container.provider(scope="tenant")
def tenant_db() -> TenantDatabase:
    return TenantDatabase()
```

#### Background jobs
```python
container.register_scope("job")

@container.provider(scope="job")
def job_context() -> JobContext:
    return JobContext()
```

#### User sessions
```python
container.register_scope("session")

@container.provider(scope="session")
def session_data() -> SessionData:
    return SessionData()
```

