from typing import List, Tuple
from .exports_model import ExportEntry

ALLOWED_OPTIONS = {
    "rw","ro","sync","async","no_root_squash","root_squash","all_squash",
    "no_subtree_check","subtree_check","insecure","secure","anonuid","anongid"
}

def validate_entries(entries: List[ExportEntry]) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    for i, e in enumerate(entries, start=1):
        # exclusión mutua básica
        if "rw" in e.options and "ro" in e.options:
            errors.append(f"[{i}] {e.path} {e.host}: 'rw' y 'ro' son excluyentes.")

        if "sync" in e.options and "async" in e.options:
            errors.append(f"[{i}] {e.path} {e.host}: 'sync' y 'async' son excluyentes.")

        # opciones desconocidas
        unknown = [o for o in e.options if o.split('=')[0] not in ALLOWED_OPTIONS]
        if unknown:
            errors.append(f"[{i}] {e.path} {e.host}: opciones no válidas: {', '.join(unknown)}")

        # anonuid/anongid deberían tener valor si se usan como anonuid=1000
        for key in ("anonuid","anongid"):
            if any(opt.startswith(f"{key}=") for opt in e.options):
                continue
            # si aparece sin '=', lo permitimos (depende de exportfs, pero lo marcamos suave)
            if key in e.options:
                errors.append(f"[{i}] {e.path} {e.host}: '{key}' debería ser '{key}=<id>'.")

    return (len(errors) == 0, errors)
