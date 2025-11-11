import re
from typing import List
from .exports_model import ExportEntry

_ALLOWED_LINE = re.compile(r'^\s*([^#\s]+)\s+(.+)$')  # path + rest (ignora comentarios)

def parse_exports(text: str) -> List[ExportEntry]:
    """
    Parsea un contenido de /etc/exports sencillo:
      /carpeta host1(rw,sync) host2(ro)
    - Ignora líneas vacías/comentarios (#)
    - No maneja líneas partidas con '\', (TODO)
    """
    entries: List[ExportEntry] = []
    for line in text.splitlines():
        raw = line.rstrip()
        if not raw.strip() or raw.strip().startswith('#'):
            continue

        m = _ALLOWED_LINE.match(raw)
        if not m:
            # línea no reconocida (se podría loguear o marcar)
            continue

        path, rest = m.group(1), m.group(2)
        # tokens tipo: host(op1,op2) host2(...) ...
        tokens = rest.split()
        for t in tokens:
            # host(opciones?)
            if '(' in t and t.endswith(')'):
                host, opts = t.split('(', 1)
                host = host.strip()
                opts = opts[:-1]  # quita ')'
                options = [o.strip() for o in opts.split(',') if o.strip()]
            else:
                # sin opciones, host "pelado"
                host = t.strip()
                options = []

            if host:
                entries.append(ExportEntry(path=path, host=host, options=options, raw=raw))
    return entries
