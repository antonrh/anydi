import datetime
import decimal
import time

import pyxdi

di = pyxdi.PyxDI(auto_register=True)


class HelloService:

    @property
    def name(self) -> str:
        return "Anton"


@di.provider(scope="singleton")
def hello() -> HelloService:
    "test"
    return HelloService()



@di.inject(lazy=True)
def handler(hello: HelloService = pyxdi.dep) -> None:
    hello_message = f"Hello, {hello.name}"


if __name__ == '__main__':
    st = datetime.datetime.utcnow()

    for n in range(10_000_000):
        handler()

    print((datetime.datetime.utcnow() - st).total_seconds())
