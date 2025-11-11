import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QTableWidget, QTableWidgetItem, QMessageBox
)
from PyQt6.QtCore import Qt

# Imports del paquete
from .utils.files import read_text
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
        self.setWindowTitle("NFS Configurator")
        self.resize(900, 520)

        title = QLabel("NFS Configurator — openSUSE 15.6")
        title.setStyleSheet("font-weight:600; font-size:16px;")

        # --- Botonera
        self.btn_load = QPushButton("📂 Cargar /etc/exports")
        self.btn_add  = QPushButton("➕ Nueva exportación")
        self.btn_validate = QPushButton("✅ Validar")
        self.btn_save_apply = QPushButton("💾 Guardar & Aplicar")

        self.btn_validate.setEnabled(False)
        self.btn_save_apply.setEnabled(False)

        self.btn_load.clicked.connect(self.on_load)
        self.btn_add.clicked.connect(self.on_add_export)
        self.btn_validate.clicked.connect(self.on_validate)
        self.btn_save_apply.clicked.connect(self.on_save_apply)

        btns = QHBoxLayout()
        btns.addWidget(self.btn_load)
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_validate)
        btns.addWidget(self.btn_save_apply)
        btns.addStretch()

        # --- Tabla
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Carpeta", "Host", "Opciones"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)

        # --- Status
        self.status = QLabel("Listo. Pulsa «Cargar /etc/exports» o «Nueva exportación».")
        self.status.setStyleSheet("color: #555;")

        # --- Layout raíz
        root = QVBoxLayout()
        root.addWidget(title)
        root.addLayout(btns)
        root.addWidget(self.table)
        root.addWidget(self.status)
        self.setLayout(root)

        # Lista en memoria con las entradas (ExportEntry)
        self._entries = []

    # --- Crear una entrada desde diálogo
    def on_add_export(self):
        dlg = ExportEditorDialog(self)
        if dlg.exec():
            entry = dlg.result_entry
            if entry:
                self._entries.append(entry)
                self.append_row(entry)
                self.btn_validate.setEnabled(True)
                self.btn_save_apply.setEnabled(True)
                self.status.setText("Añadida exportación en memoria. Aún no se guarda en /etc/exports.")

    # --- Cargar desde /etc/exports (o archivo de pruebas)
    def on_load(self):
        text = read_text(EXPORTS_PATH)
        if not text:
            QMessageBox.warning(self, "Atención", f"No se pudo leer {EXPORTS_PATH} o está vacío.")
            self.status.setText(f"No se pudo leer {EXPORTS_PATH}.")
            self.table.setRowCount(0)
            self._entries = []
            self.btn_validate.setEnabled(False)
            self.btn_save_apply.setEnabled(False)
            return

        entries = parse_exports(text)
        self._entries = entries
        self.populate_table(entries)
        self.status.setText(f"Cargado: {len(entries)} entradas desde {EXPORTS_PATH}.")
        enabled = len(entries) > 0
        self.btn_validate.setEnabled(enabled)
        self.btn_save_apply.setEnabled(enabled)

    # --- Validar las entradas actuales
    def on_validate(self):
        if not self._entries:
            QMessageBox.information(self, "Validación", "No hay entradas para validar.")
            return
        ok, errors = validate_entries(self._entries)
        if ok:
            QMessageBox.information(self, "Validación", "Todo OK ✅")
            self.status.setText("Validación correcta.")
        else:
            msg = "Se encontraron problemas:\n\n" + "\n".join(errors)
            QMessageBox.warning(self, "Validación", msg)
            self.status.setText("Validación con advertencias/errores.")

    # --- Guardar en /etc/exports y aplicar con exportfs/systemd
    def on_save_apply(self):
        if not self._entries:
            QMessageBox.information(self, "Guardar", "No hay entradas para guardar.")
            return

        # Construir texto final
        final_text = build_exports_text(self._entries)

        # Confirmación con preview
        preview = final_text if len(final_text) < 600 else final_text[:600] + "\n..."
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

    # --- Helpers de UI
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
