"""Mağazalar Arası Transfer — başlatıcı."""

import sys
import traceback

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from magaza_transfer import __version__
from magaza_transfer.ayarlar import kaynak_klasoru
from magaza_transfer.ui_ana import AnaPencere


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Mağazalar Arası Transfer")
    app.setStyle("Fusion")
    simge = kaynak_klasoru().parent / "assets" / "app.ico"
    if simge.exists():
        app.setWindowIcon(QIcon(str(simge)))

    def yakalanmamis(tur, deger, iz):
        traceback.print_exception(tur, deger, iz)
        QMessageBox.critical(None, "Beklenmeyen hata", f"{deger}")

    sys.excepthook = yakalanmamis
    pencere = AnaPencere(__version__)
    pencere.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
