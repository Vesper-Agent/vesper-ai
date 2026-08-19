import os

def get_vesper_home() -> str:
    """Returns the Vesper root directory, respecting the VESPER_HOME env var."""
    return os.path.expanduser(os.environ.get("VESPER_HOME", "~/.vesper"))

def load_env() -> None:
    """Loads KEY=VALUE pairs from a .env file in the current directory into the environment."""
    path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(path):
        return

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))
