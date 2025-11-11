import os
import time
from collections import defaultdict
from .exports_model import ExportEntry

def _group_by_path(entries):
    # Junta por path: /dir -> [ "host(opts)", "host2(opts)" ]
    groups = defaultdict(list)
    for e in entries:
        opts = ""
        if e.options:
            opts = "(" + ",".join(e.options) + ")"
        token = "{}{}".format(e.host, opts)
        groups[e.path].append(token)
    return groups

def build_exports_text(entries):
    """
    Devuelve el texto final para /etc/exports a partir de las entradas en memoria.
    Una línea por path:  /path host1(opts) host2(opts) ...
    """
    groups = _group_by_path(entries)
    lines = []
    for path in sorted(groups.keys()):
        tokens = " ".join(groups[path])
        lines.append("{} {}".format(path, tokens))
    # agrega un newline final por convención
    return "\n".join(lines) + ("\n" if lines else "")

def atomic_write_exports(target_path, text):
    """
    Escribe atomicamente:
      1) backup: /etc/exports.bak-YYYYmmddHHMMSS
      2) tmp:    /etc/exports.nfsconf.tmp
      3) rename: tmp -> /etc/exports
    """
    directory = os.path.dirname(target_path) or "."
    tmp_path = os.path.join(directory, "exports.nfsconf.tmp")
    ts = time.strftime("%Y%m%d%H%M%S")
    backup_path = os.path.join(directory, "exports.bak-{}".format(ts))

    # backup si existe
    if os.path.exists(target_path):
        with open(target_path, "rb") as f_src, open(backup_path, "wb") as f_bak:
            f_bak.write(f_src.read())

    # escribe tmp
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text)

    # permisos típicos de /etc/exports
    os.chmod(tmp_path, 0o644)

    # mueve a destino (atómico en la misma partición)
    os.replace(tmp_path, target_path)
    return backup_path if os.path.exists(backup_path) else None
