# src/nfsapp/core/validator.py
from typing import List, Tuple, Dict
from .exports_model import ExportEntry

import os
import re
import ipaddress

ALLOWED_OPTIONS = {
    "rw","ro","sync","async","no_root_squash","root_squash","all_squash",
    "no_subtree_check","subtree_check","insecure","secure","anonuid","anongid"
}

# Hostname básico (sin espacios, 1..253 chars total, labels 1..63, sin empezar/terminar con -)
_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
)

def _looks_like_host_with_opts(host: str) -> bool:
    # Ej: 10.83.178.0/24(rw,async) -> pegó opciones al host
    return "(" in host and host.endswith(")")

def _strip_opts_if_stuck(host: str) -> str:
    # Si host viene tipo 10.0.0.0/24(rw,sync) -> devuelve 10.0.0.0/24
    host = (host or "").strip()
    if _looks_like_host_with_opts(host):
        return host.split("(", 1)[0].strip()
    return host

def _is_valid_host(host: str) -> bool:
    host = _strip_opts_if_stuck(host)
    if not host:
        return False

    if host == "*":
        return True

    # IP o Red CIDR
    try:
        if "/" in host:
            ipaddress.ip_network(host, strict=False)
        else:
            ipaddress.ip_address(host)
        return True
    except ValueError:
        pass

    # Hostname
    return bool(_HOST_RE.match(host))

def _is_valid_path(path: str) -> bool:
    path = (path or "").strip()
    if not path:
        return False
    if not path.startswith("/"):
        return False
    if any(ch.isspace() for ch in path):
        return False
    return True


def validate_entries(entries: List[ExportEntry]) -> Tuple[bool, List[str]]:
    """
    Wrapper simple para mantener compatibilidad.
    Devuelve: (ok, [mensajes])
    """
    errors_by_index = validate_entries_detailed(entries)

    if not errors_by_index:
        return True, []

    messages: List[str] = []
    for idx, errs in errors_by_index.items():
        e = entries[idx]
        messages.append(f"[{idx+1}] {e.path} {e.host}: " + " | ".join(errs))

    return False, messages


def validate_entries_detailed(entries: List[ExportEntry]) -> Dict[int, List[str]]:
    """
    Retorna un dict: idx_en_lista -> [errores]
    """
    errors_by_index: Dict[int, List[str]] = {}

    for i, e in enumerate(entries):
        errs: List[str] = []

        # ---------- Validación de PATH ----------
        path = (e.path or "").strip()
        if not path:
            errs.append("Carpeta vacía. Debes seleccionar una carpeta.")
        elif not _is_valid_path(path):
            errs.append(f"Ruta de carpeta inválida: '{path}'. Debe ser absoluta, ej: /home/user/carpeta")
        else:
            # existencia real
            if not os.path.exists(path):
                errs.append(f"La carpeta no existe: {path}")
            elif not os.path.isdir(path):
                errs.append(f"La ruta no es un directorio: {path}")

        # ---------- Validación de HOST ----------
        host = (e.host or "").strip()
        if not host:
            errs.append("Host vacío. Debes indicar una IP, red (/24), hostname o '*'.")
        else:
            # Caso típico: host pegado con (opts)
            if _looks_like_host_with_opts(host):
                errs.append(
                    "El host parece incluir opciones pegadas '(...)'. "
                    "Debe ser solo host (ej: 10.83.178.0/24) y las opciones van aparte."
                )

            if not _is_valid_host(host):
                errs.append(
                    f"Host inválido: '{host}'. Usa IP (10.0.0.5), red (10.0.0.0/24), hostname (server01) o '*'."
                )

        # ---------- Opciones ----------
        opts = e.options or []

        # exclusión mutua básica
        if "rw" in opts and "ro" in opts:
            errs.append("'rw' y 'ro' son excluyentes.")

        if "sync" in opts and "async" in opts:
            errs.append("'sync' y 'async' son excluyentes.")

        # opciones desconocidas
        unknown = [o for o in opts if o.split('=')[0] not in ALLOWED_OPTIONS]
        if unknown:
            errs.append("Opciones no válidas: " + ", ".join(unknown))

        # anonuid/anongid deberían tener valor si se usan
        for key in ("anonuid", "anongid"):
            if any(opt.startswith(f"{key}=") for opt in opts):
                continue
            if key in opts:
                errs.append(f"'{key}' debería ser '{key}=<id>'.")

        if errs:
            errors_by_index[i] = errs

    return errors_by_index
