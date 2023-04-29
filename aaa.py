import time

import pyxdi

di = pyxdi.PyxDI(auto_register=True)


class HelloService:
    @property
    def name(self) -> str:
        return "Anton"



@di.inject
def handler(hello: HelloService = pyxdi.dep) -> None:
    hello_message = f"Hello, {hello}"


if __name__ == '__main__':
    st = time.process_time()
    for n in range(10000000):
        handler()
    print(time.process_time() - st)
