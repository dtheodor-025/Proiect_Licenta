from PySide6.QtWidgets import QMainWindow, QMessageBox
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile
from PySide6.QtGui import QIcon
import psycopg2
import bcrypt

DB_NAME = "Card_Database"
DB_USER = "postgres"
DB_PASSWORD = "d1234"
DB_HOST = "localhost"
DB_PORT = "5432"

class RegisterWindow(QMainWindow):
    def __init__(self, login_window):
        super().__init__()
        self.login_window = login_window

        loader = QUiLoader()
        file = QFile("register.ui")
        file.open(QFile.ReadOnly)
        self.ui = loader.load(file, self)
        file.close()

        self.resize(400, 300)

        self.setWindowTitle("OP Manager")
        self.setWindowIcon(QIcon("assets/icon.png"))

        self.ui.registerButton.clicked.connect(self.register_user)
        self.ui.backButton.clicked.connect(self.open_log_in)

    def register_user(self):
        first_name = self.ui.firstNameInput.text().strip()
        last_name = self.ui.lastNameInput.text().strip()
        email = self.ui.emailInput.text().strip()
        username = self.ui.usernameInput.text().strip()
        password = self.ui.passwordInput.text().strip()

        if not first_name or not last_name or not email or not username or not password:
            self.ui.statusLabel.setText("All fields are required.")
            return

        hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            cur = conn.cursor()

            # Insert user and return id
            cur.execute(
                """
                INSERT INTO users (email, username, password, first_name, last_name)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (email, username, hashed_pw, first_name, last_name)
            )
            user_id = cur.fetchone()[0]

            # Create collection for new user
            cur.execute(
                """
                INSERT INTO collections (user_id)
                VALUES (%s)
                """,
                (user_id,)
            )

            conn.commit()
            cur.close()
            conn.close()

            QMessageBox.information(self, "Success", "Account created successfully!")
            self.open_log_in()

        except psycopg2.Error as e:
            if "unique" in str(e).lower():
                self.ui.statusLabel.setText("Email or username already exists.")
            else:
                self.ui.statusLabel.setText("Database error.")

    def open_log_in(self):
        self.login_window.show()
        self.close()