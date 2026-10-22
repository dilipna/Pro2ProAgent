"""Pro2Pro package. Importing contracts must not initialize provider clients."""


def main() -> None:
    from .main import main as run
    run()


__all__ = ["main"]
