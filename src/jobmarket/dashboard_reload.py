"""Pick up edited dashboard modules without restarting Streamlit.

Streamlit reruns a page script when it changes, but the modules it imports from ``src/`` stay
in memory, so a running dashboard answers "module has no attribute ..." after a pull or an edit
until it is restarted. ``refresh`` is called first thing by ``dashboard/app.py``: it forgets the
dashboard modules when any of them was edited after the process started (or after we last
reloaded), so the imports that follow read the new code. A module first imported late may be
reloaded once, which is harmless.
"""

import sys
import time
from pathlib import Path

PREFIX = "jobmarket.dashboard_"
_STARTED = time.time()
_loaded_at: dict[str, float] = {}  # module name -> when we last saw it loaded


def refresh(prefix: str = PREFIX) -> list[str]:
    """Drop the modules (named ``prefix...``) when any of them was edited; returns their names.

    All of them go, not only the edited one: a module that imported the edited one keeps the old
    copy in its own namespace, so it has to be imported again as well.
    """
    loaded = {
        name: module
        for name, module in list(sys.modules.items())
        if name.startswith(prefix) and name != __name__ and getattr(module, "__file__", None)
    }
    edited = any(
        Path(str(module.__file__)).stat().st_mtime > _loaded_at.setdefault(name, _STARTED)
        for name, module in loaded.items()
    )
    if not edited:
        return []
    for name in loaded:
        del sys.modules[name]
        _loaded_at[name] = time.time()  # the copy imported next is newer than any edit so far
    return sorted(loaded)
