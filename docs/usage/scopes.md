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

### Using `from_context` for external dependencies

When a scoped provider depends on a value that will be provided at runtime via `context.set()`, register the type with `from_context=True`:

```python
from typing import Annotated

from anydi import Container


class Request:
    def __init__(self, param: str) -> None:
        self.param = param


class UserContext:
    def __init__(self, user_id: str, tenant_id: str) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id


container = Container()

# Register Request as a from_context dependency
container.register(Request, scope="request", from_context=True)


@container.provider(scope="request")
def user_context(request: Request) -> Annotated[UserContext, "current_user"]:
    return UserContext(user_id=request.param, tenant_id="tenant-1")


with container.request_context() as ctx:
    ctx.set(Request, Request(param="user-456"))

    user = container.resolve(Annotated[UserContext, "current_user"])
    assert user.user_id == "user-456"
    assert user.tenant_id == "tenant-1"
```

The `from_context=True` option tells `AnyDI` that:

1. The `Request` type will be provided via `context.set()` at runtime
2. No factory function is needed - instances are set directly in the context
3. A `LookupError` will be raised if the value is not set before resolution

This makes the dependency explicit and type-safe. The `from_context` option can only be used with scoped contexts (like `request`), not with `singleton` or `transient` scopes.

## Custom scopes

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
- `transient` providers can use any dependencies, as long as the scope they
  belong to is open

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

### Async custom scopes

Custom scopes also support async contexts:

```python
async def process_workflow() -> None:
    async with container.ascoped_context("task"):
        async with container.ascoped_context("workflow"):
            engine = await container.aresolve(WorkflowEngine)
            # Process workflow...
```

### Re-entering an active scope

Entering a scope that is already active reuses the active context, so both blocks share the same instances. Pass `isolated=True` to open a fresh, isolated context instead. It shadows the active one and is restored on exit.

```python
from anydi import Container


class TaskContext:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id


container = Container()
container.register_scope("task")
container.register(TaskContext, scope="task", from_context=True)


with container.scoped_context("task") as outer:
    outer.set(TaskContext, TaskContext(task_id="outer"))

    assert container.resolve(TaskContext).task_id == "outer"

    with container.scoped_context("task", isolated=True) as inner:
        inner.set(TaskContext, TaskContext(task_id="inner"))

        assert container.resolve(TaskContext).task_id == "inner"

    assert container.resolve(TaskContext).task_id == "outer"
```

The fresh context has its own instances. It still resolves parent and `singleton` dependencies, but inherits nothing from the context it shadows, so `from_context` values have to be set again. On exit only its own resources are closed.

This is useful when concurrent units of work each need their own scoped resources. Every task gets its own session, while the parent keeps using its own:

```python
async def handle(item: Item) -> None:
    async with container.ascoped_context("db", isolated=True):
        session = await container.aresolve(Session)
        await session.execute(insert_result(item))


async with container.ascoped_context("db"):
    session = await container.aresolve(Session)
    await session.execute(mark_batch_started())

    await asyncio.gather(*(handle(item) for item in items))

    await session.execute(mark_batch_done())
```

Without `isolated=True` all tasks would share one session, and a finished task could commit the parent's transaction.

### Best practices

1. **Clear hierarchies**: Structure scopes to match your application logic (e.g., `request` → `transaction` → `batch`)
2. **Avoid deep nesting**: Keep hierarchies simple for better performance
3. **Use clear names**: Choose names that show the scope purpose (`task`, `session`, `tenant`, etc.)
4. **Validate dependencies**: Container automatically checks that dependencies follow the hierarchy rules

### Common use cases

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

