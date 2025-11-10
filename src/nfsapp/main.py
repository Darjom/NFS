import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton

class NFSConfigurator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NFS Configurator")
        self.resize(420, 220)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Bienvenido a NFS Configurator 🖥️\n(openSUSE 15.6)"))

        btn_quit = QPushButton("Salir")
        btn_quit.clicked.connect(self.close)
        layout.addWidget(btn_quit)

        self.setLayout(layout)

def main():
    app = QApplication(sys.argv)
    win = NFSConfigurator()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
