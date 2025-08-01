import sys

if not getattr(sys, 'frozen', False):  # Only try to install packages when not frozen
    def ensure_package(package_name, import_name=None):
        import subprocess
        try:
            if import_name:
                __import__(import_name)
            else:
                __import__(package_name)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

    ensure_package("bcrypt")
    ensure_package("psycopg2")
    ensure_package("PySide6")

import bcrypt
import psycopg2
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile
from PySide6.QtGui import QIcon

from window_main import MainWindow
from register_window import RegisterWindow


DB_NAME = "Card_Database"
DB_USER = "postgres"
DB_PASSWORD = "d1234"
DB_HOST = "localhost"
DB_PORT = "5432"

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        loader = QUiLoader()
        file = QFile("login.ui")
        file.open(QFile.ReadOnly)
        self.ui = loader.load(file, self)
        file.close()

        self.resize(400, 300)

        self.setWindowTitle("OP Manager")
        self.setWindowIcon(QIcon("assets/icon.png"))

        self.ui.loginButton.clicked.connect(self.try_login)
        self.ui.registerButton.clicked.connect(self.open_register)

    def try_login(self):
        username = self.ui.usernameInput.text()
        password = self.ui.passwordInput.text()

        if self.authenticate_user(username, password):
            self.open_main_window(username)
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")

    def authenticate_user(self, username, password):
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            cur = conn.cursor()

            cur.execute("SELECT password FROM users WHERE username = %s", (username,))
            row = cur.fetchone()

            cur.close()
            conn.close()

            if row:
                stored_hash = row[0]
                if bcrypt.checkpw(password.encode(), stored_hash.encode()):
                    return True  # ✅ Login successful

            return False  # ❌ Incorrect credentials

        except psycopg2.Error as e:
            print("Database error:", e)
            return False

    def open_main_window(self, username):

        self.main = MainWindow(username)
        self.main.show()
        self.close()

    def open_register(self):
        self.register = RegisterWindow(self)
        self.register.show()
        self.hide()

if __name__ == "__main__":
    app = QApplication([])
    login = LoginWindow()
    login.show()
    app.exec()