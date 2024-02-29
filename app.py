from fastapi import FastAPI

import anydi.ext.fastapi
from anydi import Container
from anydi.ext.fastapi import Inject

container = Container()


@container.provider(scope="singleton")
def message() -> str:
    return "Hello, World!"


app = FastAPI()


@app.get("/hello")
def say_hello(message: str = Inject()) -> dict[str, str]:
    return {"message": message}


# Install the container into the FastAPI app
anydi.ext.fastapi.install(app, container)
