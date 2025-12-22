import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QTableWidget, QTableWidgetItem, QMessageBox,
    QDialog, QDialogButtonBox, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from .utils.files import read_text
from .utils.shell import run_command
from .core.exports_parser import parse_exports
from .core.validator import validate_entries_detailed
from .ui.dialogs.export_editor import ExportEditorDialog

from .core.exports_writer import build_exports_text, atomic_write_exports
from .core.nfs_service import ensure_nfs_active, apply_exports, open_firewall_services

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
        self.btn_edit = QPushButton("✏️ Editar seleccionado")
        self.btn_delete = QPushButton("🗑️ Eliminar seleccionado")
        self.btn_validate = QPushButton("✅ Validar")
        self.btn_save_apply = QPushButton("💾 Guardar & Aplicar")
        self.btn_show_active = QPushButton("🔎 Ver exportaciones activas")

        self.btn_validate.setEnabled(False)
        self.btn_save_apply.setEnabled(False)
        self.btn_edit.setEnabled(False)
        self.btn_delete.setEnabled(False)

        self.btn_load.clicked.connect(self.on_load)
        self.btn_add.clicked.connect(self.on_add_export)
        self.btn_edit.clicked.connect(self.on_edit_selected)
        self.btn_delete.clicked.connect(self.on_delete_selected)
        self.btn_validate.clicked.connect(self.on_validate)
        self.btn_save_apply.clicked.connect(self.on_save_apply)
        self.btn_show_active.clicked.connect(self.on_show_active)

        btns = QHBoxLayout()
        btns.addWidget(self.btn_load)
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_edit)
        btns.addWidget(self.btn_delete)
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
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.cellDoubleClicked.connect(self.on_edit_selected)

        # --- Status
        self.status = QLabel("Listo. Carga o agrega exportaciones. Debes VALIDAR antes de guardar.")
        self.status.setStyleSheet("color: #555;")

        root = QVBoxLayout()
        root.addWidget(title)
        root.addLayout(btns)
        root.addWidget(self.table)
        root.addWidget(self.status)
        self.setLayout(root)

        # Estado en memoria
        self._entries = []
        self._validated_ok = False
        self._row_validated = {}   # idx -> bool
        self._row_errors = {}      # idx -> [errores]

    # ----------------- Helpers de estado -----------------
    def on_selection_changed(self):
        has_sel = len(self.table.selectionModel().selectedRows()) > 0
        self.btn_edit.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel)

    def mark_all_dirty(self):
        self._validated_ok = False
        self._row_validated = {i: False for i in range(len(self._entries))}
        self._row_errors = {}
        self.btn_validate.setEnabled(bool(self._entries))
        self.btn_save_apply.setEnabled(False)
        self.refresh_row_styles()
        self.status.setText("Cambios pendientes. Debes VALIDAR antes de guardar.")

    def mark_row_dirty(self, row: int):
        self._validated_ok = False
        self._row_validated[row] = False
        self.btn_validate.setEnabled(bool(self._entries))
        self.btn_save_apply.setEnabled(False)
        self.paint_row(row)
        self.status.setText("Cambios pendientes. Debes VALIDAR antes de guardar.")

    def refresh_row_styles(self):
        for i in range(self.table.rowCount()):
            self.paint_row(i)

    def paint_row(self, row: int):
        errs = self._row_errors.get(row, [])
        validated = self._row_validated.get(row, False)

        if errs or not validated:
            bg = QColor(255, 210, 210)  # rojo suave
        else:
            bg = QColor(255, 255, 255)

        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item is not None:
                item.setBackground(bg)

    def _reindex_row_state_after_remove(self, removed_row: int):
        """Reindexa _row_validated y _row_errors cuando se elimina una fila."""
        new_validated = {}
        new_errors = {}

        for i in range(len(self._entries)):
            old_i = i if i < removed_row else i + 1
            new_validated[i] = self._row_validated.get(old_i, False)
            if old_i in self._row_errors:
                new_errors[i] = self._row_errors[old_i]

        self._row_validated = new_validated
        self._row_errors = new_errors

    def _compute_global_validated_ok(self) -> bool:
        for i in range(len(self._entries)):
            if not self._row_validated.get(i, False):
                return False
            if self._row_errors.get(i):
                return False
        return bool(self._entries)

    def _write_and_apply_current_entries(self) -> bool:
        """
        Escribe /etc/exports en base a self._entries y aplica exportfs.
        Retorna True si se aplicó OK.
        """
        final_text = build_exports_text(self._entries)
        preview = final_text if len(final_text) < 800 else final_text[:800] + "\n..."

        resp = QMessageBox.question(
            self, "Confirmar Guardar",
            "Se escribirá /etc/exports con el siguiente contenido:\n\n{}\n\n¿Continuar?".format(preview),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp != QMessageBox.StandardButton.Yes:
            return False

        backup = atomic_write_exports(EXPORTS_PATH, final_text)
        ensure_nfs_active()
        open_firewall_services()

        rc, out, err = apply_exports()
        if rc == 0:
            msg = "Cambios aplicados con éxito.\n"
            if backup:
                msg += f"Backup creado en: {backup}\n"
            if out:
                msg += "\nexportfs:\n" + out
            QMessageBox.information(self, "Aplicado", msg)
            self.status.setText("Guardado y aplicado correctamente.")
            return True

        QMessageBox.warning(self, "exportfs", f"exportfs -ra devolvió código {rc}:\n{err}")
        self.status.setText("Guardado, pero problemas aplicando exportfs.")
        return False

    # ----------------- Acciones UI -----------------
    def on_add_export(self):
        dlg = ExportEditorDialog(self)
        if dlg.exec():
            entry = dlg.result_entry
            if entry:
                self._entries.append(entry)
                self.append_row(entry)

                row = self.table.rowCount() - 1
                self._row_validated[row] = False
                self._row_errors.pop(row, None)

                self._validated_ok = False
                self.btn_validate.setEnabled(True)
                self.btn_save_apply.setEnabled(False)
                self.paint_row(row)
                self.status.setText("Añadida exportación. Pendiente de VALIDAR antes de guardar.")

    def on_load(self):
        text = read_text(EXPORTS_PATH)
        if not text:
            QMessageBox.warning(self, "Atención", f"No se pudo leer {EXPORTS_PATH} o está vacío.")
            self.table.setRowCount(0)
            self._entries = []
            self._validated_ok = False
            self._row_validated = {}
            self._row_errors = {}
            self.btn_validate.setEnabled(False)
            self.btn_save_apply.setEnabled(False)
            self.status.setText(f"No se pudo leer {EXPORTS_PATH}.")
            return

        entries = parse_exports(text)
        self._entries = entries
        self.populate_table(entries)

        
        self.mark_loaded_clean()

        self.status.setText(
            f"Cargado: {len(entries)} entradas desde {EXPORTS_PATH}. "
            f"Estado: OK (ya aplicado en el sistema)."
        )

    def on_edit_selected(self, *_):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        if row < 0 or row >= len(self._entries):
            return

        current = self._entries[row]
        dlg = ExportEditorDialog(self)

        # precargar
        try:
            dlg.path_edit.setText(current.path)
            dlg.host_edit.setText(current.host)

            opts_set = set(current.options or [])
            for cb in dlg.checks:
                cb.setChecked(cb.text() in opts_set)

            known = set(cb.text() for cb in dlg.checks)
            extras = [o for o in (current.options or []) if o not in known]
            dlg.extra_opts.setText(",".join(extras))
        except Exception:
            pass

        if dlg.exec():
            edited = dlg.result_entry
            if edited:
                self._entries[row] = edited
                self.table.setItem(row, 0, QTableWidgetItem(edited.path))
                self.table.setItem(row, 1, QTableWidgetItem(edited.host))
                self.table.setItem(row, 2, QTableWidgetItem(", ".join(edited.options)))
                self.table.resizeColumnsToContents()

                self._row_errors.pop(row, None)
                self.mark_row_dirty(row)

    def on_delete_selected(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        if row < 0 or row >= len(self._entries):
            return

        entry = self._entries[row]

        # Mensaje con 2 modos: solo lista, o lista + sistema
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Eliminar exportación")
        box.setText(
            "¿Qué deseas hacer con la exportación seleccionada?\n\n"
            f"- Carpeta: {entry.path}\n"
            f"- Host: {entry.host}\n"
            f"- Opciones: {', '.join(entry.options)}"
        )
        btn_list = box.addButton("Solo eliminar de la lista", QMessageBox.ButtonRole.AcceptRole)
        btn_system = box.addButton("Eliminar y aplicar al sistema (/etc/exports)", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(btn_cancel)
        box.exec()

        clicked = box.clickedButton()
        if clicked == btn_cancel:
            return

        # 1) eliminar de memoria + tabla
        self._entries.pop(row)
        self.table.removeRow(row)
        self._reindex_row_state_after_remove(row)

        # tras eliminar, recalcular estado global y estilos
        self._validated_ok = self._compute_global_validated_ok()
        self.btn_validate.setEnabled(bool(self._entries))
        self.btn_save_apply.setEnabled(self._validated_ok and bool(self._entries))
        self.refresh_row_styles()

        self.status.setText("Fila eliminada de la lista. Valida si corresponde antes de guardar.")

        # 2) si el usuario pidió eliminar también del sistema, aplicamos ahora
        if clicked == btn_system:
            if not self._entries:
                # si ya no queda nada, igual se puede escribir archivo vacío, pero es delicado:
                confirm_empty = QMessageBox.question(
                    self, "Archivo vacío",
                    "No quedan exportaciones en la lista.\n\n"
                    "Esto dejará /etc/exports vacío (sin exportaciones).\n"
                    "¿Continuar?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if confirm_empty != QMessageBox.StandardButton.Yes:
                    return

            # Validar lo que queda antes de tocar /etc/exports
            errors_by_idx = validate_entries_detailed(self._entries)
            self._row_errors = {idx: errs for idx, errs in errors_by_idx.items()}
            for i in range(len(self._entries)):
                self._row_validated[i] = (i not in errors_by_idx)
            self.refresh_row_styles()

            if errors_by_idx:
                self._validated_ok = False
                self.btn_save_apply.setEnabled(False)
                QMessageBox.warning(
                    self, "No se aplicó al sistema",
                    "Se eliminó de la lista, pero NO se modificó /etc/exports porque quedaron filas inválidas (en rojo).\n\n"
                    "Corrige, valida y recién aplica."
                )
                return

            # OK: aplicar al sistema
            try:
                self._validated_ok = True
                self.btn_save_apply.setEnabled(True)
                self.status.setText("Todo OK. Aplicando cambios al sistema…")
                self._write_and_apply_current_entries()
            except PermissionError:
                QMessageBox.critical(
                    self, "Permisos",
                    "Permiso denegado al escribir /etc/exports o al ejecutar comandos.\n\n"
                    "Ejecuta la app con privilegios (pkexec o sudo -E)."
                )
            except Exception as ex:
                QMessageBox.critical(self, "Error", f"Ocurrió un error aplicando la eliminación:\n{ex}")

    def on_validate(self):
        if not self._entries:
            QMessageBox.information(self, "Validación", "No hay entradas para validar.")
            return

        errors_by_idx = validate_entries_detailed(self._entries)
        self._row_errors = {idx: errs for idx, errs in errors_by_idx.items()}

        for i in range(len(self._entries)):
            self._row_validated[i] = (i not in errors_by_idx)

        self.refresh_row_styles()

        self._validated_ok = (len(errors_by_idx) == 0) and bool(self._entries)
        self.btn_save_apply.setEnabled(self._validated_ok and bool(self._entries))

        if self._validated_ok:
            QMessageBox.information(self, "Validación", "Todo OK ✅")
            self.status.setText("Validación correcta. Ya puedes Guardar & Aplicar.")
        else:
            msgs = []
            for idx, errs in errors_by_idx.items():
                e = self._entries[idx]
                msgs.append(f"[{idx+1}] {e.path} {e.host}: " + " | ".join(errs))
            msg = "Se encontraron problemas:\n\n" + "\n".join(msgs)
            QMessageBox.warning(self, "Validación", msg)
            self.status.setText("Hay filas inválidas (en rojo). Corrige y vuelve a validar.")

    def on_save_apply(self):
        if not self._entries:
            QMessageBox.information(self, "Guardar", "No hay entradas para guardar.")
            return

        if not self._validated_ok:
            QMessageBox.warning(
                self, "Validación requerida",
                "Aún hay filas inválidas o pendientes (rojas).\n\n"
                "Corrige y presiona VALIDAR hasta que todo esté OK ✅."
            )
            return

        try:
            self._write_and_apply_current_entries()
        except PermissionError:
            QMessageBox.critical(
                self, "Permisos",
                "Permiso denegado al escribir /etc/exports o al ejecutar comandos.\n\n"
                "Ejecuta la app con privilegios (pkexec o sudo -E)."
            )
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Ocurrió un error guardando o aplicando:\n{ex}")

    def on_show_active(self):
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

    # ----------------- Helpers de tabla -----------------
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
    
    def mark_loaded_clean(self):
        self._row_validated = {i: True for i in range(len(self._entries))}
        self._row_errors = {}
        self._validated_ok = True

        self.btn_validate.setEnabled(bool(self._entries))
        self.btn_save_apply.setEnabled(False)  # no hay nada que "guardar" si solo cargaste
        self.refresh_row_styles()



def main():
    app = QApplication(sys.argv)
    win = NFSConfigurator()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
