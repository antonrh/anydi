from fastapi import FastAPI
from anydi import Container
import uvicorn
from typing import Any, Annotated
from anydi.ext.fastapi import install, Inject

class Service:
    def __init__(self, name: str) -> None:
        self.name = name

container = Container()

@container.provider(scope="singleton")
def service() -> Annotated[Service, "service"]:
    return Service("service")

app = FastAPI()

@app.get("/")
def index(service: Annotated[Annotated[Service, "service"], Inject()]) -> Any:
    return {"service": service.name}


install(app, container)


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8005)
