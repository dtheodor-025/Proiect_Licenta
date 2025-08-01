import psycopg2
import re
from PySide6.QtWidgets import (
    QMainWindow, QLabel, QVBoxLayout, QWidget,
    QComboBox, QGridLayout, QMessageBox, QLineEdit, QPushButton, QListWidget,
    QListWidgetItem, QHBoxLayout, QInputDialog, QMenu
)
from PySide6.QtGui import QPixmap, QGuiApplication, QPainter
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt, QEvent, QPoint

DB_NAME = "Card_Database"
DB_USER = "postgres"
DB_PASSWORD = "d1234"
DB_HOST = "localhost"
DB_PORT = "5432"

class MainWindow(QMainWindow):
    def __init__(self, username):
        super().__init__()
        loader = QUiLoader()
        file = QFile("main_window.ui")
        file.open(QFile.ReadOnly)
        self.ui = loader.load(file, self)
        file.close()

        self.deck_list_widget = self.ui.findChild(QListWidget, "deckListWidget")
        self.deck_list_widget.itemDoubleClicked.connect(self.remove_card_on_double_click)
        self.setup_decklist_context_menu()
        self.add_deck_button = self.ui.findChild(QPushButton, "addDeckButton")

        self.save_deck_button = self.ui.findChild(QPushButton, "saveDeckButton")
        self.cancel_deck_button = self.ui.findChild(QPushButton, "cancelDeckButton")

        self.add_deck_button.clicked.connect(self.add_deck)
        if self.save_deck_button:
            self.save_deck_button.clicked.connect(self.finish_deck)
            self.save_deck_button.setVisible(False)
        if self.cancel_deck_button:
            self.cancel_deck_button.clicked.connect(self.cancel_deck)
            self.cancel_deck_button.setVisible(False)

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.showFullScreen()

        self.editing_deck_id = None

        header_layout = QHBoxLayout()

        self.decklist_title_label = self.ui.findChild(QLabel, "decklistsTitle")  # your decklist title
        self.show_all_button = QPushButton("Show All")
        self.show_all_button.setStyleSheet("font-size: 14px; padding: 6px 12px; font-weight: bold;")
        self.show_all_button.clicked.connect(self.load_user_decks)

        decklist_title_layout = self.ui.findChild(QVBoxLayout, "sidebarLayout")  # the layout with title label
        if decklist_title_layout:
            header_layout.addWidget(self.decklist_title_label)
            header_layout.addStretch()  # Pushes button to the right
            header_layout.addWidget(self.show_all_button)
            decklist_title_layout.insertLayout(0, header_layout)

        self.username = username
        self.deck_building = False
        self.current_leader = None
        self.current_deck = {}

        self.ui.scrollArea.setWidget(self.ui.findChild(QWidget, "scrollAreaWidgetContents"))

        self.cardGrid = self.ui.findChild(QGridLayout, "gridLayout")
        self.search_input = self.ui.findChild(QLineEdit, "searchInput")
        self.add_button = self.ui.findChild(QPushButton, "addButton")

        self.suggestion_list = QListWidget(self)
        self.suggestion_list.setFocusPolicy(Qt.NoFocus)
        self.suggestion_list.hide()

        self.cost_dropdown = self.findChild(QComboBox, "costDropdown")
        self.cost_dropdown.currentIndexChanged.connect(self.apply_filters)

        self.type_dropdown = self.findChild(QComboBox, "typeDropdown")
        self.type_dropdown.currentIndexChanged.connect(self.apply_filters)

        self.color_dropdown = self.findChild(QComboBox, "colorDropdown")
        self.color_dropdown.currentIndexChanged.connect(self.apply_filters)

        self.search_input.textChanged.connect(self.show_suggestions)
        self.search_input.textChanged.connect(self.apply_filters)
        self.search_input.installEventFilter(self)
        self.suggestion_list.itemClicked.connect(self.select_suggestion)
        self.add_button.clicked.connect(self.add_card_to_user)

        screen_geometry = QGuiApplication.primaryScreen().availableGeometry()
        screen_width = screen_geometry.width()
        screen_hight = screen_geometry.height()

        self.overlayWidget = QWidget(self)
        self.overlayWidget.setVisible(False)
        self.overlayWidget.setStyleSheet("background-color: black; border: 2px solid white;")
        self.overlayWidget.setFixedSize(int(screen_width * 0.327), int(screen_hight * 0.945))

        overlay_layout = QVBoxLayout(self.overlayWidget)
        overlay_layout.setContentsMargins(5, 5, 5, 5)
        overlay_layout.setSpacing(10)

        self.overlayImage = QLabel()
        self.overlayImage.setScaledContents(True)
        self.overlayImage.setFixedSize(int(screen_width * 0.32), int(screen_hight * 0.85))
        self.overlayImage.setAlignment(Qt.AlignCenter)
        self.overlayImage.setContextMenuPolicy(Qt.CustomContextMenu)
        self.overlayImage.customContextMenuRequested.connect(lambda _: self.overlayWidget.hide())

        self.addOverlayButton = QPushButton("Add")
        self.removeOverlayButton = QPushButton("Remove")
        self.addOverlayButton.clicked.connect(self.handle_overlay_add)
        self.removeOverlayButton.clicked.connect(self.handle_overlay_remove)

        self.addOverlayButton.setStyleSheet("font-size: 16px; padding: 10px 20px; min-width: 100px; font-weight: bold;")
        self.removeOverlayButton.setStyleSheet("font-size: 16px; padding: 10px 20px; min-width: 100px; font-weight: bold;")

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setAlignment(Qt.AlignCenter)
        button_layout.setSpacing(20)
        button_layout.addWidget(self.addOverlayButton)
        button_layout.addWidget(self.removeOverlayButton)

        overlay_layout.addWidget(self.overlayImage)
        overlay_layout.addWidget(button_row)

        self.header_label = self.ui.findChild(QLabel, "titleLabel")
        if self.header_label:
            self.header_label.setText(f"{username}'s Collection")
            self.header_label.setStyleSheet("font-size: 28px; font-weight: bold; color: white; padding: 10px;")
            self.header_label.setAlignment(Qt.AlignCenter)

        self.collection_count_label = self.ui.findChild(QLabel, "collectionCountLabel")

        self.setCentralWidget(self.ui)

        self.minimize_btn = self.ui.findChild(QPushButton, "minimizeButton")
        self.close_btn = self.ui.findChild(QPushButton, "closeButton")
        if self.minimize_btn:
            self.minimize_btn.clicked.connect(self.showMinimized)
        if self.close_btn:
            self.close_btn.clicked.connect(self.show_exit_dialog)

        self.load_user_cards()
        self.load_user_decks()

    def show_exit_dialog(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Exit Options")
        dialog.setText("What do you want to do?")
        dialog.setIcon(QMessageBox.Question)
        logout_button = dialog.addButton("Log out", QMessageBox.AcceptRole)
        close_button = dialog.addButton("Close application", QMessageBox.DestructiveRole)
        cancel_button = dialog.addButton("Cancel", QMessageBox.RejectRole)

        dialog.exec()

        if dialog.clickedButton() == logout_button:
            from log_in import LoginWindow
            self.login = LoginWindow()
            self.login.show()
            self.close()
        elif dialog.clickedButton() == close_button:
            self.close()

    def add_deck(self):
        self.deck_building = True
        self.current_leader = None
        self.current_deck = {}
        self.save_deck_button.setVisible(False)
        self.cancel_deck_button.setVisible(True)
        self.deck_list_widget.clear()
        self.header_label.setText("Select a Leader (1)")
        leader_cards = [c for c in self.get_user_cards(self.username) if c[4] == "Leader"]
        self.display_cards(leader_cards)

    def setup_decklist_context_menu(self):
        self.deck_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.deck_list_widget.customContextMenuRequested.connect(self.show_deck_context_menu)

    def update_collection_counter(self):
        cards = self.get_user_cards(self.username)
        total = sum(card[6] for card in cards)  # count este la indexul 6
        if self.collection_count_label:
            self.collection_count_label.setText(f"Total Cards in Collection: {total}")

    def remove_card_on_double_click(self, item):
        if not self.deck_building:
            return

        item_text = item.text()
        match = re.match(r"^(.*)\s+\(x(\d+)\)$", item_text)
        if not match:
            return

        card_name = match.group(1).strip()
        count = int(match.group(2))

        # Find the card_id in current_deck
        card_id_to_remove = None
        for card_id, (card_obj, card_count) in self.current_deck.items():
            if card_obj[1] == card_name:
                card_id_to_remove = card_id
                break

        if card_id_to_remove is None:
            return

        # Decrease or remove
        if self.current_deck[card_id_to_remove][1] > 1:
            self.current_deck[card_id_to_remove] = (
                self.current_deck[card_id_to_remove][0],
                self.current_deck[card_id_to_remove][1] - 1
            )
        else:
            del self.current_deck[card_id_to_remove]

        self.update_deck_list()

        self.apply_filters([c for c in self.get_user_cards(self.username)
                    if c[4] != "Leader" and any(color in c[3] for color in self.current_leader[3])])


    def show_deck_context_menu(self, position):
        item = self.deck_list_widget.itemAt(position)
        if not item:
            return

        deck_name = item.text()
        menu = QMenu()
        show_action = menu.addAction("Show Deck")
        remove_action = menu.addAction("Remove Deck")

        action = menu.exec(self.deck_list_widget.mapToGlobal(position))
        if action == show_action:
            self.display_deck_cards(deck_name)
        elif action == remove_action:
            self.remove_deck(deck_name)

    def display_deck_cards(self, deck_name):
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            cur = conn.cursor()

            deck_name_clean = re.sub(r'\s*\(Leader:.*\)\s*$', '', deck_name)


            cur.execute("""
                SELECT d.id, c.card_id, c.name, c.image, c.colors, c.type, c.cost
                FROM decks d
                JOIN users u ON d.user_id = u.id
                JOIN cards c ON d.leader_card_id = c.id
                WHERE d.name = %s AND u.username = %s
            """, (deck_name_clean, self.username))
            result = cur.fetchone()

            if not result:
                QMessageBox.warning(self, "Deck Not Found", "The selected deck was not found.")
                return

            deck_id, leader_card_id, name, image, colors, type_, cost = result
            self.editing_deck_id = deck_id
            self.deck_building = True
            self.save_deck_button.setVisible(True)
            self.cancel_deck_button.setVisible(True)
            self.deck_list_widget.clear()


            self.current_leader = (leader_card_id, name, image, colors, type_, cost, 1)
            self.current_deck = {leader_card_id: (self.current_leader, 1)}
            self.deck_list_widget.addItem(f"Leader: {name}")


            cur.execute("""
                SELECT c.card_id, c.name, c.image, c.colors, c.type, c.cost, dc.count
                FROM deck_cards dc
                JOIN cards c ON dc.card_id = c.id
                WHERE dc.deck_id = %s
            """, (deck_id,))
            rows = cur.fetchall()

            for card in rows:
                if card[4] == "Leader":
                    continue
                self.current_deck[card[0]] = (card, card[6])  # card + count
                self.deck_list_widget.addItem(f"{card[1]} (x{card[6]})")

            total_cards = sum(count for _, count in self.current_deck.values())
            self.header_label.setText(f"Select 50 Cards: {total_cards - 1}/50")


            filtered = [c for c in self.get_user_cards(self.username)
                        if c[4] != "Leader" and any(color in c[3] for color in self.current_leader[3])]
            self.apply_filters(filtered)

            cur.close()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Error Showing Deck", str(e))

    def apply_filters(self, card_list: list = []):
        text = self.search_input.text().strip().lower()
        cost_text = self.cost_dropdown.currentText()
        type_text = self.type_dropdown.currentText()
        color_text = self.color_dropdown.currentText()

        if card_list is [] or type(card_list) is int or type(card_list) is str:
            all_cards = self.get_user_cards(self.username)
            if self.current_leader:
                if len(self.current_leader) is 1:
                    color_text = self.current_leader[3][0]
                else:
                    color_text = self.current_leader[3]
        else:
            all_cards = card_list



        filtered_cards = []

        for card in all_cards:

            name_matches = text in card[1].lower()
            cost_matches = (cost_text == "All" or str(card[5]) == cost_text)
            type_matches = (type_text == "All" or card[4] == type_text)

            # Colors field is a list of strings
            color_matches = (
                    color_text == "All" or
                    (isinstance(card[3], list) and color_text in card[3])
            )
            if self.current_leader:
                if len(self.current_leader) is not 1:
                    color_matches = (set(card[3]).issubset(self.current_leader[3]))

            if name_matches and cost_matches and type_matches and color_matches:
                filtered_cards.append(card)

        if self.deck_building is False:
            self.load_user_cards_parameter(filtered_cards)
        else:
            self.display_cards(filtered_cards)

    def remove_deck(self, deck_name):
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            cur = conn.cursor()

            deck_name = re.sub(r'\s*\(Leader:.*\)\s*$', '', deck_name)

            cur.execute("""
                DELETE FROM decks
                USING users
                WHERE decks.user_id = users.id
                  AND decks.name = %s
                  AND users.username = %s
            """, (deck_name, self.username))

            conn.commit()
            cur.close()
            conn.close()

            self.load_user_decks()  # Refresh deck list after removal

        except Exception as e:
            QMessageBox.critical(self, "Error Removing Deck", str(e))

    def finish_deck(self):
        total_cards = sum(count for (_, count) in self.current_deck.values())
        if total_cards != 51:
            QMessageBox.warning(self, "Incomplete Deck", "A full deck must contain 51 cards (1 leader + 50).")
            return

        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = %s", (self.username,))
            user_id = cur.fetchone()[0]

            cur.execute("SELECT id FROM cards WHERE card_id = %s", (self.current_leader[0],))
            leader_card_id = cur.fetchone()[0]

            if self.editing_deck_id:  # Updating existing deck
                cur.execute("""
                    UPDATE decks SET leader_card_id = %s WHERE id = %s
                """, (leader_card_id, self.editing_deck_id))

                cur.execute("DELETE FROM deck_cards WHERE deck_id = %s", (self.editing_deck_id,))

                for card_id, (card_data, count) in self.current_deck.items():
                    cur.execute("SELECT id FROM cards WHERE card_id = %s", (card_id,))
                    card_db_id = cur.fetchone()[0]
                    cur.execute("""
                        INSERT INTO deck_cards (deck_id, card_id, count)
                        VALUES (%s, %s, %s)
                    """, (self.editing_deck_id, card_db_id, count))

                QMessageBox.information(self, "Deck Updated", f"Deck updated successfully.")
            else:  # Creating new deck
                deck_name, ok = QInputDialog.getText(self, "Save Deck", "Enter a name for this deck:")
                if not (ok and deck_name):
                    return

                cur.execute("""
                    INSERT INTO decks (user_id, name, leader_card_id) VALUES (%s, %s, %s)
                    RETURNING id
                """, (user_id, deck_name, leader_card_id))
                deck_id = cur.fetchone()[0]

                for card_id, (card_data, count) in self.current_deck.items():
                    cur.execute("SELECT id FROM cards WHERE card_id = %s", (card_id,))
                    card_db_id = cur.fetchone()[0]
                    cur.execute("""
                        INSERT INTO deck_cards (deck_id, card_id, count)
                        VALUES (%s, %s, %s)
                    """, (deck_id, card_db_id, count))

                QMessageBox.information(self, "Deck Saved", f"Deck '{deck_name}' saved with 51 cards.")

            conn.commit()
            cur.close()
            conn.close()

            self.cancel_deck()

        except Exception as e:
            QMessageBox.critical(self, "Save Deck Error", str(e))

    def cancel_deck(self):
        self.editing_deck_id = None
        self.deck_building = False
        self.current_leader = None
        self.current_deck = {}
        self.save_deck_button.setVisible(False)
        self.cancel_deck_button.setVisible(False)
        self.header_label.setText("Collection")
        self.load_user_cards()
        self.load_user_decks()

    def on_card_selected(self, card):
        if not self.deck_building:
            return

        card_id, name, image, colors, type_, cost, available_count = card

        if self.current_leader is None:
            if type_ != "Leader":
                return
            self.current_leader = card
            self.current_deck[card_id] = (card, 1)
            self.deck_list_widget.clear()
            self.deck_list_widget.addItem(f"Leader: {name}")
            self.save_deck_button.setVisible(True)
            self.header_label.setText("Select 50 Cards: 0/50")

            allowed_colors = set(colors)
            filtered = [c for c in self.get_user_cards(self.username)
                        if c[4] != "Leader" and any(color in c[3] for color in allowed_colors)]
            self.apply_filters(filtered)
        else:
            total_cards = sum(count for _, count in self.current_deck.values())
            if total_cards >= 51:
                QMessageBox.warning(self, "Deck Full", "You've already selected 51 cards.")
                return

            current_count = self.current_deck.get(card_id, (card, 0))[1]
            if current_count >= min(4, available_count):
                return  # Already at max copies

            self.current_deck[card_id] = (card, current_count + 1)
            self.update_deck_list()
            self.apply_filters([c for c in self.get_user_cards(self.username)
                                if c[4] != "Leader" and any(color in c[3] for color in self.current_leader[3])])
            self.header_label.setText(f"Select 50 Cards: {total_cards}/50")

    def update_deck_list(self):
        self.deck_list_widget.clear()
        leader = next(((card, count) for card_id, (card, count) in self.current_deck.items() if card[4] == "Leader"),
                      None)
        if leader:
            self.deck_list_widget.addItem(f"Leader: {leader[0][1]}")

        for card_id, (card, count) in self.current_deck.items():
            if card[4] == "Leader":
                continue
            self.deck_list_widget.addItem(f"{card[1]} (x{count})")

        match = re.search(r"Select 50 Cards: (\d+)/50", self.header_label.text())
        if match:
            current_count = int(match.group(1))
            new_count = current_count -1
        self.header_label.setText(f"Select 50 Cards: {new_count}/50")

    def display_cards(self, cards):
        layout = self.cardGrid
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        layout.setSpacing(10)
        row, col = 0, 0

        for card in cards:
            card_id, name, image, colors, type_, cost, count = card
            container = QWidget()
            vbox = QVBoxLayout()

            pixmap = QPixmap(image)
            if pixmap.isNull():
                pixmap = QPixmap(120, 180)
                pixmap.fill(Qt.darkGray)
            pixmap = pixmap.scaled(240, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            current_count = self.current_deck.get(card_id, (card, 0))[1]
            if current_count >= min(4, count):
                gray_overlay = QPixmap(pixmap.size())
                gray_overlay.fill(Qt.transparent)

                painter = QPainter(gray_overlay)
                painter.setBrush(Qt.gray)
                painter.setOpacity(0.5)
                painter.drawRect(pixmap.rect())
                painter.end()

                painter = QPainter(pixmap)
                painter.drawPixmap(0, 0, gray_overlay)
                painter.end()

            image_label = QLabel()
            image_label.setPixmap(pixmap)
            image_label.setAlignment(Qt.AlignCenter)

            name_label = QLabel(f"{card_id} {name} (x{count})")
            name_label.setAlignment(Qt.AlignHCenter)
            name_label.setWordWrap(True)
            name_label.setStyleSheet("font-weight: bold;")

            vbox.addWidget(image_label)
            vbox.addWidget(name_label)
            container.setLayout(vbox)
            layout.addWidget(container, row, col)

            def make_handler(card_data):
                def handler():
                    self.on_card_selected(card_data)
                return handler

            image_label.mousePressEvent = lambda event, c=card: make_handler(c)()

            col += 1
            if col >= 4:
                col = 0
                row += 1


    def eventFilter(self, source, event):
        try:
            if source == self.search_input and event.type() == QEvent.KeyPress:
                if event.key() in (Qt.Key_Down, Qt.Key_Up):
                    count = self.suggestion_list.count()
                    if count == 0:
                        return False

                    current_row = self.suggestion_list.currentRow()
                    if event.key() == Qt.Key_Down:
                        new_row = (current_row + 1) % count
                    else:
                        new_row = (current_row - 1 + count) % count

                    self.suggestion_list.setCurrentRow(new_row)
                    return True

                elif event.key() == Qt.Key_Return and self.suggestion_list.currentItem():
                    self.select_suggestion(self.suggestion_list.currentItem())
                    return True
        except Exception as e:
            print("Event filter error:", e)
        return super().eventFilter(source, event)

    def show_suggestions(self, text):
        self.suggestion_list.clear()
        if not text.strip():
            self.suggestion_list.hide()
            return

        results = self.query_card_suggestions(text)
        if not results:
            self.suggestion_list.hide()
            return

        for card_id, name in results:
            item = QListWidgetItem(f"{card_id} - {name}")
            item.setData(Qt.UserRole, card_id)
            self.suggestion_list.addItem(item)

        self.suggestion_list.setCurrentRow(0)
        self.suggestion_list.resize(self.search_input.width(), min(200, self.suggestion_list.sizeHintForRow(0) * len(results)))
        pos = self.search_input.mapToGlobal(self.search_input.rect().bottomLeft())
        self.suggestion_list.move(pos)
        self.suggestion_list.show()
        self.search_input.show()

    def select_suggestion(self, item):
        if item:
            self.search_input.setText(item.text())
        self.suggestion_list.hide()

    def add_card_to_user(self):
        text = self.search_input.text().strip()
        if not text:
            return

        if " - " in text:
            card_id = text.split(" - ")[0]
        else:
            card_id = text

        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            cur = conn.cursor()

            cur.execute("SELECT id FROM users WHERE username = %s", (self.username,))
            user_id = cur.fetchone()
            if not user_id:
                raise Exception("User not found")
            user_id = user_id[0]

            cur.execute("SELECT id FROM collections WHERE user_id = %s", (user_id,))
            collection_id = cur.fetchone()
            if not collection_id:
                raise Exception("Collection not found")
            collection_id = collection_id[0]

            cur.execute("SELECT id FROM cards WHERE card_id = %s", (card_id,))
            card_result = cur.fetchone()
            if not card_result:
                raise Exception("Card not found")
            card_db_id = card_result[0]

            cur.execute("""
                INSERT INTO collection_cards (collection_id, card_id, count)
                VALUES (%s, %s, 1)
                ON CONFLICT (collection_id, card_id) DO UPDATE
                SET count = collection_cards.count + 1
            """, (collection_id, card_db_id))

            conn.commit()
            cur.close()
            conn.close()

            self.load_user_cards()
            self.search_input.clear()
            self.suggestion_list.hide()

        except Exception as e:
            QMessageBox.critical(self, "Add Card Error", str(e))

    def query_card_suggestions(self, text):
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            cur = conn.cursor()
            cur.execute("""
                SELECT card_id, name
                FROM cards
                WHERE card_id ILIKE %s OR name ILIKE %s
                LIMIT 10
            """, (f"%{text}%", f"%{text}%"))
            results = cur.fetchall()
            cur.close()
            conn.close()
            return results
        except Exception as e:
            print("Query Error:", e)
            return []

    def load_user_decks(self):
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            cur = conn.cursor()
            cur.execute("""
                SELECT decks.id, decks.name, cards.name
                FROM decks
                JOIN users ON decks.user_id = users.id
                JOIN cards ON decks.leader_card_id = cards.id
                WHERE users.username = %s
            """, (self.username,))
            decks = cur.fetchall()
            self.deck_list_widget.clear()
            for deck_id, name, leader_name in decks:
                item = QListWidgetItem(f"{name} (Leader: {leader_name})")
                item.setData(Qt.UserRole, deck_id)
                self.deck_list_widget.addItem(item)

            cur.close()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Load Decks Error", str(e))

    def load_user_cards(self):
        cards = self.get_user_cards(self.username)
        self.update_collection_counter()
        if self.header_label:
            self.header_label.setText(f"{self.username}'s Collection")
            self.header_label.setStyleSheet("font-size: 28px; font-weight: bold; color: white; padding: 10px;")
            self.header_label.setAlignment(Qt.AlignCenter)

        layout = self.cardGrid
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        layout.setSpacing(10)
        row, col = 0, 0

        for card in cards:
            card_id, name, image, colors, type_, cost, count = card
            container = QWidget()
            vbox = QVBoxLayout()

            pixmap = QPixmap(image)
            if pixmap.isNull():
                pixmap = QPixmap(120, 180)
                pixmap.fill(Qt.darkGray)

            pixmap = pixmap.scaled(240, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            image_label = QLabel()
            image_label.setPixmap(pixmap)
            image_label.setAlignment(Qt.AlignCenter)

            name_label = QLabel(f"{card_id} {name} (x{count})")
            name_label.setAlignment(Qt.AlignHCenter)
            name_label.setWordWrap(True)
            name_label.setStyleSheet("font-weight: bold;")

            vbox.addWidget(image_label)
            vbox.addWidget(name_label)
            container.setLayout(vbox)
            layout.addWidget(container, row, col)

            def make_handler(card_id, image_path):
                def handler():
                    if self.overlayWidget.isVisible():
                        self.overlayWidget.hide()
                        return

                    pixmap = QPixmap(image_path)
                    if pixmap.isNull():
                        return

                    self.overlayImage.setPixmap(pixmap)

                    main_center_x = self.width() // 2
                    main_center_y = self.height() // 2
                    w, h = self.overlayWidget.width(), self.overlayWidget.height()
                    self.overlayWidget.move(self.mapToGlobal(QPoint(main_center_x - w // 2, main_center_y - h // 2)))
                    self.overlayWidget.show()

                    self.overlayWidget.card_id = card_id
                return handler

            image_label.mousePressEvent = lambda event, cid=card_id, img=image: make_handler(cid, img)()

            col += 1
            if col >= 4:
                col = 0
                row += 1

    def load_user_cards_parameter(self, user_cards):
        cards = user_cards

        layout = self.cardGrid
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        layout.setSpacing(10)
        row, col = 0, 0

        for card in cards:
            card_id, name, image, colors, type_, cost, count = card
            container = QWidget()
            vbox = QVBoxLayout()

            pixmap = QPixmap(image)
            if pixmap.isNull():
                pixmap = QPixmap(120, 180)
                pixmap.fill(Qt.darkGray)

            pixmap = pixmap.scaled(240, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            image_label = QLabel()
            image_label.setPixmap(pixmap)
            image_label.setAlignment(Qt.AlignCenter)

            name_label = QLabel(f"{card_id} {name} (x{count})")
            name_label.setAlignment(Qt.AlignHCenter)
            name_label.setWordWrap(True)
            name_label.setStyleSheet("font-weight: bold;")

            vbox.addWidget(image_label)
            vbox.addWidget(name_label)
            container.setLayout(vbox)
            layout.addWidget(container, row, col)

            def make_handler(card_id, image_path):
                def handler():
                    if self.overlayWidget.isVisible():
                        self.overlayWidget.hide()
                        return

                    pixmap = QPixmap(image_path)
                    if pixmap.isNull():
                        return

                    self.overlayImage.setPixmap(pixmap)

                    main_center_x = self.width() // 2
                    main_center_y = self.height() // 2
                    w, h = self.overlayWidget.width(), self.overlayWidget.height()
                    self.overlayWidget.move(self.mapToGlobal(QPoint(main_center_x - w // 2, main_center_y - h // 2)))
                    self.overlayWidget.show()

                    self.overlayWidget.card_id = card_id
                return handler

            image_label.mousePressEvent = lambda event, cid=card_id, img=image: make_handler(cid, img)()

            col += 1
            if col >= 4:
                col = 0
                row += 1

    def get_user_cards(self, username):
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            cur = conn.cursor()
            cur.execute(""" 
                SELECT
                    cards.card_id,
                    cards.name,
                    cards.image,
                    cards.colors,
                    cards.type,
                    cards.cost,
                    collection_cards.count
                FROM users
                JOIN collections ON collections.user_id = users.id
                JOIN collection_cards ON collection_cards.collection_id = collections.id
                JOIN cards ON cards.id = collection_cards.card_id
                WHERE users.username = %s
            """, (username,))
            cards = cur.fetchall()
            cur.close()
            conn.close()
            return cards
        except Exception as e:
            QMessageBox.critical(self, "Database Error", str(e))
            return []

    def handle_overlay_add(self):
        card_id = getattr(self.overlayWidget, "card_id", None)
        if card_id:
            self.search_input.setText(card_id)
            self.add_card_to_user()

    def handle_overlay_remove(self):
        card_id = getattr(self.overlayWidget, "card_id", None)
        if not card_id:
            return

        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            cur = conn.cursor()

            cur.execute("SELECT id FROM users WHERE username = %s", (self.username,))
            user_id = cur.fetchone()[0]

            cur.execute("SELECT id FROM collections WHERE user_id = %s", (user_id,))
            collection_id = cur.fetchone()[0]

            cur.execute("SELECT id FROM cards WHERE card_id = %s", (card_id,))
            card_db_id = cur.fetchone()[0]

            # Get current count
            cur.execute("""
                SELECT count FROM collection_cards
                WHERE collection_id = %s AND card_id = %s
            """, (collection_id, card_db_id))
            result = cur.fetchone()

            if result and result[0] > 1:
                cur.execute("""
                    UPDATE collection_cards
                    SET count = count - 1
                    WHERE collection_id = %s AND card_id = %s
                """, (collection_id, card_db_id))
            else:
                cur.execute("""
                    DELETE FROM collection_cards
                    WHERE collection_id = %s AND card_id = %s
                """, (collection_id, card_db_id))

            conn.commit()
            cur.close()
            conn.close()

            self.load_user_cards()
        except Exception as e:
            QMessageBox.critical(self, "Remove Card Error", str(e))

if __name__ == "__main__":
    # Only run this if window_main.py is executed directly, not when imported
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    window = MainWindow("test_user")  # or some dummy value
    window.show()
    sys.exit(app.exec())