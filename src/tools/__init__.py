"""Tool package. load_all() imports every tool module so ALL entry points
(listen.py, talk.py, hello_jarvis.py) expose the identical capability set."""
import importlib
import pkgutil


def load_all() -> list[str]:
    loaded = []
    for m in pkgutil.iter_modules(__path__):
        if not m.name.startswith("_"):
            importlib.import_module(f"tools.{m.name}")
            loaded.append(m.name)
    return loaded
