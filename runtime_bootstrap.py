from pathlib import Path
import site


def ensure_local_site_packages():
    user_root = Path.home() / "AppData" / "Roaming" / "Python"

    for candidate in user_root.glob("Python*/site-packages"):
        site.addsitedir(str(candidate))
