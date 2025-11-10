#!/usr/bin/env bash
set -e

echo "==> Refrescando repos…"
sudo zypper ref

echo "==> Instalando runtimes base para Qt6/PyQt6…"
# Nota: 'freetype2' es provisto por libfreetype6 en Leap
sudo zypper -n in \
  libX11-6 libxcb1 libxcb-xfixes0 libxcb-shape0 libxcb-keysyms1 libxcb-icccm4 \
  libxcb-render0 libxcb-randr0 libxkbcommon0 libxkbcommon-x11-0 \
  libfreetype6 fontconfig glib2-tools libglib-2_0-0 || true

echo "==> Buscando proveedor de libgthread-2.0.so.0()(64bit)…"
PKG="$(sudo zypper search --provides --match-exact 'libgthread-2.0.so.0()(64bit)' \
  | awk '/^\s*[ips]\s*\|/ {print $3}' | head -n1 || true)"

if [ -n "$PKG" ]; then
  echo "→ Instalando proveedor encontrado: $PKG"
  sudo zypper -n in "$PKG"
else
  echo "⚠️  No se encontró proveedor vía search; intentando con libgthread-2_0-0 directamente…"
  sudo zypper -n in libgthread-2_0-0 || {
    echo "❌ No se pudo instalar libgthread-2_0-0. Verifica que el repo OSS/Update esté habilitado."
    echo "   Sugerencia: sudo zypper lr -u   y revisa que existan repo-oss y update-oss de Leap 15.6"
    exit 1
  }
fi

echo "==> Actualizando caché del linker…"
/sbin/ldconfig || sudo /sbin/ldconfig

if /sbin/ldconfig -p | grep -q 'libgthread-2.0.so.0'; then
  echo "✅ libgthread-2.0.so.0 disponible en el sistema."
  echo "   Ejecuta tu app dentro del venv:  python -m src.nfsapp.main"
else
  echo "❌ Aún no aparece libgthread-2.0.so.0 en la caché."
  echo "   Comparte la salida de estos comandos:"
  echo "   - sudo zypper lr -u"
  echo "   - sudo zypper search --provides --match-exact 'libgthread-2.0.so.0()(64bit)'"
  exit 1
fi
