from anydi import Container


class Request:
    def __init__(self, path: str) -> None:
        self.path = path


container = Container(strict=False)


@container.provider(scope="request")
def name(request: Request) -> str:
    return f"AnyDI - {request.path}"


with container.request_context() as ctx:
    # ctx.set(Request, instance=Request("path1"))
    print(container.resolve(str))

# with container.request_context() as ctx:
#     print(container.resolve(str))
