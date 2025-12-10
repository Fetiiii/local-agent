from __future__ import annotations

import sys
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Local GPT Agent")
        self.resize(1280, 900)

        # Permissive settings so local file:// can reach http://127.0.0.1:5000
        if hasattr(QWebEngineSettings, "globalSettings"):
            gs = QWebEngineSettings.globalSettings()
            gs.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            gs.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            gs.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)

        view = QWebEngineView()
        settings = view.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)

        page_settings = view.page().settings()
        page_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        page_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        page_settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)

        profile_settings = view.page().profile().settings()
        profile_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        profile_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        profile_settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)

        html_path = Path(__file__).resolve().parent / "ui" / "assets" / "index.html"
        view.load(QUrl.fromLocalFile(str(html_path)))
        self.setCentralWidget(view)


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
