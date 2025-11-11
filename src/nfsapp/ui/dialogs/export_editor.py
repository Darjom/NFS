# src/nfsapp/ui/dialogs/export_editor.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QCheckBox, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt
from ...core.exports_model import ExportEntry

ALLOWED_OPTS = [
    "rw", "ro", "sync", "async", "no_root_squash", "root_squash", "all_squash",
    "no_subtree_check", "subtree_check", "insecure", "secure"
]

class ExportEditorDialog(QDialog):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Nueva exportación NFS")
        self.setModal(True)

        # --- Campos
        self.path_edit = QLineEdit()
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("Ej: 192.168.1.0/24 o nombre-de-host")

        browse_btn = QPushButton("Examinar…")
        browse_btn.clicked.connect(self.browse_folder)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Carpeta:"))
        path_row.addWidget(self.path_edit)
        path_row.addWidget(browse_btn)

        host_row = QHBoxLayout()
        host_row.addWidget(QLabel("Host:"))
        host_row.addWidget(self.host_edit)

        # Checkboxes para opciones conocidas
        self.checks = []
        opts_layout = QVBoxLayout()
        opts_layout.addWidget(QLabel("Opciones:"))
        checks_row = QHBoxLayout()
        col = QVBoxLayout()
        half = (len(ALLOWED_OPTS) + 1) // 2
        for i, name in enumerate(ALLOWED_OPTS):
            cb = QCheckBox(name)
            self.checks.append(cb)
            if i < half:
                col.addWidget(cb)
            else:
                # armar segunda columna
                pass
        checks_row.addLayout(col)
        col2 = QVBoxLayout()
        for i, name in enumerate(ALLOWED_OPTS[half:]):
            cb = self.checks[half + i]
            col2.addWidget(cb)
        checks_row.addLayout(col2)
        opts_layout.addLayout(checks_row)

        # Campo libre para otras opciones (ej: anonuid=1000,anongid=1000)
        self.extra_opts = QLineEdit()
        self.extra_opts.setPlaceholderText("Opciones extra separadas por coma (ej: anonuid=1000,anongid=1000)")

        extra_row = QHBoxLayout()
        extra_row.addWidget(QLabel("Extras:"))
        extra_row.addWidget(self.extra_opts)

        # Botones
        btn_ok = QPushButton("Agregar")
        btn_cancel = QPushButton("Cancelar")
        btn_ok.clicked.connect(self.on_accept)
        btn_cancel.clicked.connect(self.reject)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(btn_cancel)
        actions.addWidget(btn_ok)

        # Layout raíz
        root = QVBoxLayout()
        root.addLayout(path_row)
        root.addLayout(host_row)
        root.addLayout(opts_layout)
        root.addLayout(extra_row)
        root.addLayout(actions)
        self.setLayout(root)

        self.result_entry = None  # ExportEntry a devolver

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta a compartir")
        if folder:
            self.path_edit.setText(folder)

    def on_accept(self):
        path = self.path_edit.text().strip()
        host = self.host_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Falta carpeta", "Selecciona una carpeta.")
            return
        if not host:
            QMessageBox.warning(self, "Falta host", "Ingresa un host (IP/CIDR o hostname).")
            return

        options = [cb.text() for cb in self.checks if cb.isChecked()]

        extra = self.extra_opts.text().strip()
        if extra:
            # separar por coma y agregar
            extras = [p.strip() for p in extra.split(",") if p.strip()]
            options.extend(extras)

        # armar línea cruda (raw) a modo referencia visual
        opts_str = ""
        if options:
            opts_str = "(" + ",".join(options) + ")"
        raw = "{} {}{}".format(path, host, opts_str)

        self.result_entry = ExportEntry(path=path, host=host, options=options, raw=raw)
        self.accept()
