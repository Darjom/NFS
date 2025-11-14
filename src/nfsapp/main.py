import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QTableWidget, QTableWidgetItem, QMessageBox,
    QDialog, QDialogButtonBox, QTextEdit
)
from PyQt6.QtCore import Qt

from .utils.files import read_text
from .utils.shell import run_command
from .core.exports_parser import parse_exports
from .core.validator import validate_entries
from .ui.dialogs.export_editor import ExportEditorDialog

from .core.exports_writer import build_exports_text, atomic_write_exports
from .core.nfs_service import ensure_nfs_active, apply_exports, open_firewall_services

# En desarrollo puedes apuntar a un archivo local para pruebas (ej.: "./exports_demo")
EXPORTS_PATH = "/etc/exports"

class NFSConfigurator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NFS Configurator — openSUSE 15.6")
        self.resize(950, 560)

        title = QLabel("NFS Configurator — openSUSE 15.6")
        title.setStyleSheet("font-weight:600; font-size:16px;")

        # --- Botonera
        self.btn_load = QPushButton("📂 Cargar /etc/exports")
        self.btn_add  = QPushButton("➕ Nueva exportación")
        self.btn_validate = QPushButton("✅ Validar")
        self.btn_save_apply = QPushButton("💾 Guardar & Aplicar")
        self.btn_show_active = QPushButton("🔎 Ver exportaciones activas")

        self.btn_validate.setEnabled(False)
        self.btn_save_apply.setEnabled(False)

        self.btn_load.clicked.connect(self.on_load)
        self.btn_add.clicked.connect(self.on_add_export)
        self.btn_validate.clicked.connect(self.on_validate)
        self.btn_save_apply.clicked.connect(self.on_save_apply)
        self.btn_show_active.clicked.connect(self.on_show_active)

        btns = QHBoxLayout()
        btns.addWidget(self.btn_load)
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_validate)
        btns.addWidget(self.btn_save_apply)
        btns.addWidget(self.btn_show_active)
        btns.addStretch()

        # --- Tabla
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Carpeta", "Host", "Opciones"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)

        # --- Status
        self.status = QLabel("Listo. Carga o agrega exportaciones. Debes VALIDAR antes de guardar.")
        self.status.setStyleSheet("color: #555;")

        # --- Layout raíz
        root = QVBoxLayout()
        root.addWidget(title)
        root.addLayout(btns)
        root.addWidget(self.table)
        root.addWidget(self.status)
        self.setLayout(root)

        # Estado en memoria
        self._entries = []
        self._validated_ok = False  # <- obligatorio validar antes de guardar

    # ---------- Cambios de estado ----------
    def mark_dirty(self):
        """Se llamó a Cargar o Añadir; obliga a validar otra vez."""
        self._validated_ok = False
        self.btn_validate.setEnabled(bool(self._entries))
        self.btn_save_apply.setEnabled(False)
        self.status.setText("Cambios pendientes. Debes VALIDAR antes de guardar.")

    # ---------- Acciones de UI ----------
    def on_add_export(self):
        dlg = ExportEditorDialog(self)
        if dlg.exec():
            entry = dlg.result_entry
            if entry:
                self._entries.append(entry)
                self.append_row(entry)
                self.mark_dirty()

    def on_load(self):
        text = read_text(EXPORTS_PATH)
        if not text:
            QMessageBox.warning(self, "Atención", f"No se pudo leer {EXPORTS_PATH} o está vacío.")
            self.table.setRowCount(0)
            self._entries = []
            self._validated_ok = False
            self.btn_validate.setEnabled(False)
            self.btn_save_apply.setEnabled(False)
            self.status.setText(f"No se pudo leer {EXPORTS_PATH}.")
            return

        entries = parse_exports(text)
        self._entries = entries
        self.populate_table(entries)
        self.mark_dirty()
        self.status.setText(f"Cargado: {len(entries)} entradas desde {EXPORTS_PATH}. Debes VALIDAR antes de guardar.")

    def on_validate(self):
        if not self._entries:
            QMessageBox.information(self, "Validación", "No hay entradas para validar.")
            return
        ok, errors = validate_entries(self._entries)
        if ok:
            self._validated_ok = True
            self.btn_save_apply.setEnabled(True)
            QMessageBox.information(self, "Validación", "Todo OK ✅")
            self.status.setText("Validación correcta. Ya puedes Guardar & Aplicar.")
        else:
            self._validated_ok = False
            self.btn_save_apply.setEnabled(False)
            msg = "Se encontraron problemas:\n\n" + "\n".join(errors)
            QMessageBox.warning(self, "Validación", msg)
            self.status.setText("Validación con advertencias/errores. Corrige y vuelve a validar.")

    def on_save_apply(self):
        if not self._entries:
            QMessageBox.information(self, "Guardar", "No hay entradas para guardar.")
            return
        if not self._validated_ok:
            QMessageBox.warning(self, "Validación requerida", "Debes validar las entradas antes de guardar.")
            return

        # Construir texto final
        final_text = build_exports_text(self._entries)

        # Confirmación con preview
        preview = final_text if len(final_text) < 800 else final_text[:800] + "\n..."
        resp = QMessageBox.question(
            self, "Confirmar Guardar",
            "Se escribirá /etc/exports con el siguiente contenido:\n\n{}\n\n¿Continuar?".format(preview)
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        try:
            # Escribir /etc/exports de forma atómica + backup
            backup = atomic_write_exports("/etc/exports", final_text)

            # Asegurar servicio activo y abrir firewall (si disponible)
            ensure_nfs_active()
            open_firewall_services()

            # Aplicar exportaciones
            rc, out, err = apply_exports()
            if rc == 0:
                msg = "Cambios aplicados con éxito.\n"
                if backup:
                    msg += f"Backup creado en: {backup}\n"
                if out:
                    msg += "\nexportfs:\n" + out
                QMessageBox.information(self, "Aplicado", msg)
                self.status.setText("Guardado y aplicado correctamente.")
            else:
                QMessageBox.warning(self, "exportfs", f"exportfs -ra devolvió código {rc}:\n{err}")
                self.status.setText("Guardado, pero problemas aplicando exportfs.")
        except PermissionError:
            QMessageBox.critical(
                self, "Permisos",
                "Permiso denegado al escribir /etc/exports o al ejecutar comandos.\n\n"
                "Ejecuta la app con privilegios (p. ej., usando pkexec o sudo -E)."
            )
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Ocurrió un error guardando o aplicando:\n{ex}")

    def on_show_active(self):
        """Muestra lo que el kernel NFS tiene exportado realmente (exportfs -v)."""
        rc, out, err = run_command(["/usr/sbin/exportfs", "-v"])
        text = out if rc == 0 else f"(error {rc})\n{err}"

        dlg = QDialog(self)
        dlg.setWindowTitle("Exportaciones activas (exportfs -v)")
        dlg.resize(700, 420)
        layout = QVBoxLayout(dlg)

        txt = QTextEdit(dlg)
        txt.setReadOnly(True)
        txt.setPlainText(text if text.strip() else "No hay exportaciones activas.")
        txt.setFontFamily("monospace")
        layout.addWidget(txt)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dlg)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)

        dlg.exec()

    # ---------- Helpers de UI ----------
    def append_row(self, e):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(e.path))
        self.table.setItem(row, 1, QTableWidgetItem(e.host))
        self.table.setItem(row, 2, QTableWidgetItem(", ".join(e.options)))
        self.table.resizeColumnsToContents()

    def populate_table(self, entries):
        self.table.setRowCount(0)
        for e in entries:
            self.append_row(e)

def main():
    app = QApplication(sys.argv)
    win = NFSConfigurator()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
