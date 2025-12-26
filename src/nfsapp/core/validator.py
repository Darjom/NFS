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

def _opt_key(opt: str) -> str:
    return opt.split("=", 1)[0].strip()

def _parse_kv(opt: str):
    # retorna (key, value|None)
    if "=" in opt:
        k, v = opt.split("=", 1)
        return k.strip(), v.strip()
    return opt.strip(), None

def _validate_options_coherence(opts: List[str]) -> List[str]:
    errs: List[str] = []
    if not opts:
        errs.append("No se especificaron opciones. Recomiendo al menos 'rw' o 'ro' y 'sync'.")
        return errs

    # Normalizar
    keys = [_opt_key(o) for o in opts]

    # Duplicados (misma key repetida)
    dup_keys = sorted({k for k in keys if keys.count(k) > 1})
    # permitir duplicados solo si son distintas keys (no aplica), así que error
    if dup_keys:
        errs.append("Opciones duplicadas: " + ", ".join(dup_keys))

    has = set(keys)

    # Acceso
    if "rw" in has and "ro" in has:
        errs.append("'rw' y 'ro' son excluyentes.")
    elif "rw" not in has and "ro" not in has:
        errs.append("Falta modo de acceso: agrega 'rw' o 'ro'.")

    # sync/async
    if "sync" in has and "async" in has:
        errs.append("'sync' y 'async' son excluyentes.")
    # (opcional) si quieres forzarlo:
    # elif "sync" not in has and "async" not in has:
    #     errs.append("Falta modo de escritura: recomienda 'sync' (o 'async' si sabes lo que haces).")

    # secure/insecure
    if "secure" in has and "insecure" in has:
        errs.append("'secure' e 'insecure' son excluyentes.")

    # subtree_check
    if "subtree_check" in has and "no_subtree_check" in has:
        errs.append("'subtree_check' y 'no_subtree_check' son excluyentes.")

    # root_squash
    if "root_squash" in has and "no_root_squash" in has:
        errs.append("'root_squash' y 'no_root_squash' son excluyentes.")

    # all_squash coherencia
    if "all_squash" in has and "no_root_squash" in has:
        errs.append("'all_squash' no es coherente con 'no_root_squash' (all_squash anonimiza a todos).")

    # anonuid/anongid formato
    kv = dict()
    for o in opts:
        k, v = _parse_kv(o)
        if v is not None:
            kv[k] = v

    for k in ("anonuid", "anongid"):
        if k in kv:
            if kv[k] == "":
                errs.append(f"'{k}=' no puede estar vacío.")
            elif not kv[k].isdigit():
                errs.append(f"'{k}=' debe ser numérico. Ej: {k}=1000")

    # Recomendación cuando hay squash
    if ("all_squash" in has or "root_squash" in has) and ("anonuid" not in kv or "anongid" not in kv):
        errs.append("Si usas *squash*, se recomienda definir anonuid=<id> y anongid=<id> para controlar el usuario anónimo.")

    return errs



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
            if not os.path.exists(path):
                errs.append(f"La carpeta no existe: {path}")
            elif not os.path.isdir(path):
                errs.append(f"La ruta no es un directorio: {path}")

        # ---------- Validación de HOST ----------
        host = (e.host or "").strip()
        if not host:
            errs.append("Host vacío. Debes indicar una IP, red (/24), hostname o '*'.")
        else:
            if _looks_like_host_with_opts(host):
                errs.append(
                    "El host parece incluir opciones pegadas '(...)'. "
                    "Debe ser solo host (ej: 10.83.178.0/24) y las opciones van aparte."
                )

            if not _is_valid_host(host):
                errs.append(
                    f"Host inválido: '{host}'. Usa IP (10.0.0.5), red (10.0.0.0/24), hostname (server01) o '*' ."
                )

        # ---------- Opciones ----------
        opts = [o.strip() for o in (e.options or []) if o and o.strip()]
        opt_keys = [o.split("=", 1)[0].strip() for o in opts]
        opt_set = set(opt_keys)

        # Duplicados (misma key repetida, ej: rw,rw o anonuid=1,anonuid=2)
        dup_keys = sorted({k for k in opt_keys if opt_keys.count(k) > 1})
        if dup_keys:
            errs.append("Opciones duplicadas: " + ", ".join(dup_keys))

        # Modo de acceso
        if "rw" in opt_set and "ro" in opt_set:
            errs.append("'rw' y 'ro' son excluyentes.")
        elif "rw" not in opt_set and "ro" not in opt_set:
            errs.append("Falta modo de acceso: agrega 'rw' o 'ro'.")

        # sync/async
        if "sync" in opt_set and "async" in opt_set:
            errs.append("'sync' y 'async' son excluyentes.")

        # secure/insecure
        if "secure" in opt_set and "insecure" in opt_set:
            errs.append("'secure' e 'insecure' son excluyentes.")

        # subtree_check/no_subtree_check
        if "subtree_check" in opt_set and "no_subtree_check" in opt_set:
            errs.append("'subtree_check' y 'no_subtree_check' son excluyentes.")

        # root_squash/no_root_squash
        if "root_squash" in opt_set and "no_root_squash" in opt_set:
            errs.append("'root_squash' y 'no_root_squash' son excluyentes.")

        # all_squash coherencia
        if "all_squash" in opt_set and "no_root_squash" in opt_set:
            errs.append("'all_squash' no es coherente con 'no_root_squash' (all_squash anonimiza a todos).")

        # opciones desconocidas
        unknown = [o for o in opts if o.split("=", 1)[0].strip() not in ALLOWED_OPTIONS]
        if unknown:
            errs.append("Opciones no válidas: " + ", ".join(unknown))

        # anonuid/anongid formato + recomendación cuando hay squash
        kv = {}
        for o in opts:
            if "=" in o:
                k, v = o.split("=", 1)
                kv[k.strip()] = v.strip()

        for key in ("anonuid", "anongid"):
            if key in kv:
                if kv[key] == "":
                    errs.append(f"'{key}=' no puede estar vacío.")
                elif not kv[key].isdigit():
                    errs.append(f"'{key}=' debe ser numérico. Ej: {key}=1000")
            elif key in opt_set:
                errs.append(f"'{key}' debería ser '{key}=<id>'.")

        if ("all_squash" in opt_set or "root_squash" in opt_set) and ("anonuid" not in kv or "anongid" not in kv):
            errs.append("Si usas *squash*, se recomienda definir anonuid=<id> y anongid=<id>.")

        if errs:
            errors_by_index[i] = errs

    return errors_by_index
