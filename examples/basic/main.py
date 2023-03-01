import pyxdi
from examples.basic.handlers import create_user, get_user, get_users


def main() -> None:
    di = pyxdi.PyxDI()
    di.scan(["examples.basic"])
    di.start()

    user = create_user(email="demo@mail.com")

    assert get_users() == [user]
    assert get_user(email="demo@mail.com") == user

    di.close()


if __name__ == "__main__":
    main()
