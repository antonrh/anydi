import pyxdi


@pyxdi.provider(tags=["a", "a1", "provider"])
def a_a1_provider() -> str:
    return "a.a1.str_provider"
