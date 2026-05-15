import logging
logger = logging.getLogger(__name__)

import os
import uuid
from PyQt5 import QtWidgets, QtGui, QtCore
from .workers import OpenSession


class Ui_Form:
    """
    A PyQt5 UI form class for configuring and executing network diagnostics.

    """

    def setup_ui(self, form):
        """
        Set up the layout and UI elements of the diagnostics form.

        Args:
            form (QWidget): The parent widget to apply the layout and components to.
        """
        self.form = form
        self.layout = QtWidgets.QVBoxLayout(self.form)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(5)

        self._setup_top_panel()
        self._setup_session_tabs()

    def _setup_top_panel(self):
        """Initializes the input bar and connect button layout."""
        self.top_panel = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.top_panel)

        self.device_input = QtWidgets.QLineEdit(self.form)
        self.device_input.setFixedHeight(30)
        self.device_input.setPlaceholderText(
            "Comma separated devices e.g. (host1, host2, host3...)"
        )
        self.top_panel.addWidget(self.device_input)

        self.connect_button = QtWidgets.QPushButton("Connect", parent=self.form)
        self.connect_button.setFixedSize(150, 30)
        self.top_panel.addWidget(self.connect_button)

    def _setup_session_tabs(self):
        """Initializes the tab widget to manage multiple terminal sessions."""
        self.sessions_tab_widget = Sessions(self)
        self.layout.addWidget(self.sessions_tab_widget)


class Sessions(QtWidgets.QTabWidget):
    """
    Manages multiple terminal sessions in a tabbed interface.
    """

    def __init__(self, form):
        super().__init__(form)
        self.form = form
        self.data = {}
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_tab)

        self.setStyleSheet("""
            QTabWidget {
                border: None;
            }
            QTabBar::tab {
                min-width: 120px;
                padding: 4px;
            }
            QTabWidget::pane {
                border: 1px solid #d3d3d3;
            }
        """)

    def add_session(self, name):
        """
        Adds a new session tab with the given device name.
        """
        logger.debug(f"Adding session for device: {name}")
        session_widget = Session(self, name, self.currentIndex() + 1)
        self.addTab(session_widget, name)
        self.setCurrentWidget(session_widget)

        self.data[session_widget.session_id] = {
            'index': self.currentIndex(),
            "name": name,
            "widget": session_widget
        }

    def close_tab(self, index):
        """
        Closes the session tab at the specified index.
        """
        widget = self.widget(index)
        for session_id, info in list(self.data.items()):
            if info["widget"] == widget:
                logger.debug(f"Closing session: {info['name']}")
                widget.close_session()
                del self.data[session_id]
                break
        self.removeTab(index)
        widget.deleteLater()


class Session(QtWidgets.QWidget):
    """
    Represents a single terminal session.
    Handles connection, command input, and displaying output.
    """

    def __init__(self, sessions, name, index):
        super().__init__()
        self.sessions = sessions
        self.name = name
        self.index = index
        self.session_id = str(uuid.uuid4())

        logger.debug(f"Initializing session: {name}")

        session_params = {
            'username': self.sessions.form.session['NETWORK_USERNAME'],
            'password': self.sessions.form.session['NETWORK_PASSWORD'],
            'proxy': {
                'hostname': self.sessions.form.session['JUMPHOST_IP'],
                'username': self.sessions.form.session['JUMPHOST_USERNAME'],
                'password': self.sessions.form.session['JUMPHOST_PASSWORD'],
            },
            'handler': 'NETMIKO',
            'hostname': name
        }

        self.worker = OpenSession(**session_params)
        self.worker.return_text.connect(self.add_card)
        self.worker.session_failed.connect(self.add_card)
        self.worker.start()

        self.prompt = ''
        self._setup_ui()

    def _setup_ui(self):
        """
        Sets up the UI components for the session.
        """
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
            }

            /* Vertical ScrollBar */
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 0px;
            }

            QScrollBar::handle:vertical {
                background: #d3d3d3;
                border-radius: 5px;
                min-height: 20px;
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }

            /* Horizontal ScrollBar */
            QScrollBar:horizontal {
                background: transparent;
                height: 10px;
                margin: 0px;
            }

            QScrollBar::handle:horizontal {
                background: #d3d3d3;
                border-radius: 5px;
                min-width: 20px;
            }

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }

            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)

        self._init_loader()
        self._init_scroll_area()
        self._init_input()

    def _init_loader(self):
        """
        Initializes the loading animation and message.
        """
        self.loader_widget = QtWidgets.QWidget()
        self.loader_layout = QtWidgets.QHBoxLayout(self.loader_widget)
        self.loader_layout.setSpacing(10)
        self.loader_layout.addItem(
            QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))

        self.loader_message = QtWidgets.QLabel('Connecting..')
        self.loader_message.setAlignment(QtCore.Qt.AlignCenter)
        self.loader_layout.addWidget(self.loader_message)

        self.loader_label = QtWidgets.QLabel()
        self.loader_label.setAlignment(QtCore.Qt.AlignCenter)
        self.loader_movie = QtGui.QMovie(os.path.join(os.path.dirname(__file__), 'assets', 'loading.gif'))
        self.loader_label.setMovie(self.loader_movie)
        self.loader_movie.start()
        self.loader_layout.addWidget(self.loader_label)

        self.loader_layout.addItem(
            QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
        self.layout.addWidget(self.loader_widget)

    def _init_scroll_area(self):
        """
        Initializes the scroll area for session output.
        """
        self.scroll_area = QtWidgets.QScrollArea()
        self.apply_scroll_area_theme()
        self.scroll_area.hide()
        self.scroll_area.setWidgetResizable(True)
        self.layout.addWidget(self.scroll_area)

        self.content_widget = QtWidgets.QWidget()
        self.scroll_area.setWidget(self.content_widget)

        self.content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        self.cards_layout = QtWidgets.QVBoxLayout()
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(0)
        self.content_layout.addLayout(self.cards_layout)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        line.setLineWidth(1)
        line.setFixedHeight(1)
        line.setStyleSheet("color: #d3d3d3; background-color: #d3d3d3;")
        self.content_layout.addWidget(line)

    def _init_input(self):
        """
        Initializes the command input field.
        """
        self.input_text_edit = CommandTextEdit()
        self.input_text_edit.return_pressed.connect(self.handle_command)
        self.content_layout.addWidget(self.input_text_edit)
        self.content_layout.addItem(
            QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding))

    def handle_command(self, text):
        """
        Handles execution of a command entered by the user.
        """
        if self.worker:
            logger.debug(f"Executing command on {self.name}: {text}")
            self.worker.execute_command(text)

    def close_session(self):
        """
        Closes the current session connection.
        """
        logger.info(f"Closing session: {self.name}")
        self.worker.close()

    def add_card(self, data):
        """
        Adds an output card to the UI with response data.
        """
        if self.scroll_area.isHidden():
            self.loader_widget.deleteLater()
            self.scroll_area.show()

        self.input_text_edit.set_prompt(data.get('prompt', ''))

        if data.get('prompt'):
            self.sessions.setTabText(self.index, data.get('prompt')[:-2])

        if data.get('output'):
            output_card = Card(self, data)
            self.cards_layout.addWidget(output_card)
            QtCore.QTimer.singleShot(0, self.input_text_edit.setFocus)
            QtCore.QTimer.singleShot(0, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        """
        Scrolls the output area to the bottom.
        """
        self.content_widget.adjustSize()
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def apply_scroll_area_theme(self):
        """
        Applies theme to scroll area based on palette.
        """
        color = self.sessions.palette().color(QtGui.QPalette.WindowText)
        bg_color = '#ffffff' if QtGui.QColor(color).lightness() < 128 else '#343434'
        self.scroll_area.setStyleSheet(f"background-color: {bg_color}; border: none;")


class Card(QtWidgets.QWidget):
    """
    Displays session command output including raw text and parsed table data.
    """

    def __init__(self, session, data):
        super().__init__(session)
        self.data = data
        logger.debug("Creating output card.")

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(0)

        color = session.palette().color(QtGui.QPalette.WindowText)
        bg_color = '#f5f5f5' if QtGui.QColor(color).lightness() < 128 else '#1c1c1c'

        self.setStyleSheet(f"""
            QWidget {{
                border-radius: 3px;
                border: 1px solid #d3d3d3;
                background-color: {bg_color};
            }}
            QTextEdit, QLabel {{
                border: none;
            }}
            QTableWidget {{
                border: 1px solid #d3d3d3;
            }}
        """)

        self.add_label()
        self.add_table()

    def add_label(self):
        """
        Adds a read-only label showing the prompt and raw output.
        """
        logger.debug("Adding label output area.")
        self.label = QtWidgets.QLabel(self)
        self.label.setTextFormat(QtCore.Qt.RichText)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse | QtCore.Qt.LinksAccessibleByMouse)
        self.layout.addWidget(self.label)

        prompt = self.data.get('prompt', '')
        output = self.data.get('output', '').lstrip().replace('\n', '<br>')

        html = (
            f'<span style="color:green; font-weight:bold;">{prompt}</span>'
            f'<span style="white-space:pre-wrap; font-weight:300;">{output}</span>'
        )
        self.label.setText(html)

    def add_table(self):
        """
        Adds a table if structured parsed data exists, otherwise displays error message.
        """
        parsed_data = self.data.get('parsed')
        if isinstance(parsed_data, list) and parsed_data:
            logger.debug("Parsed table data found. Adding table.")
            headers = [header.replace("_", " ").title() for header in parsed_data[0].keys()]
            table = CopyableTable(self)
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setHighlightSections(False)
            table.horizontalHeader().setFixedHeight(30)
            for row_index, item in enumerate(parsed_data):
                table.insertRow(row_index)
                for col_index, value in enumerate(item.values()):
                    item_widget = QtWidgets.QTableWidgetItem(str(value))
                    font = item_widget.font()
                    font.setWeight(QtGui.QFont.Light)
                    item_widget.setFont(font)
                    table.setItem(row_index, col_index, item_widget)
                    table.setRowHeight(row_index, 30)

            header = table.horizontalHeader()
            for col in range(table.columnCount()):
                mode = QtWidgets.QHeaderView.Stretch if col == table.columnCount() - 1 else QtWidgets.QHeaderView.ResizeToContents
                header.setSectionResizeMode(col, mode)

            table.setFixedHeight(int((len(parsed_data) + 1) * 30.5))
            self.layout.addWidget(table)
        else:
            logger.warning("Parsed data invalid or missing.")
            error_label = QtWidgets.QLabel(f"[TextFSM Error] {parsed_data}")
            error_label.setWordWrap(True)
            error_label.setStyleSheet('color: red;')
            error_label.setFixedHeight(40)
            self.layout.addWidget(error_label)


class CopyableTable(QtWidgets.QTableWidget):
    """
    QTableWidget that supports copying selected content to clipboard.
    """

    def keyPressEvent(self, event):
        if event.matches(QtGui.QKeySequence.Copy):
            logger.debug("Copy event detected. Copying selection.")
            self.copy_selection_to_clipboard()
        else:
            super().keyPressEvent(event)

    def copy_selection_to_clipboard(self):
        """
        Copies selected table range (including headers) to clipboard as TSV.
        """
        selection = self.selectedRanges()
        if not selection:
            logger.info("No selection to copy.")
            return

        copied_text = ""
        left_col = selection[0].leftColumn()
        right_col = selection[0].rightColumn()

        headers = [
            self.horizontalHeaderItem(col).text()
            for col in range(left_col, right_col + 1)
        ]
        copied_text += "\t".join(headers) + "\n"

        for row in range(selection[0].topRow(), selection[0].bottomRow() + 1):
            row_data = [
                self.item(row, col).text() if self.item(row, col) else ""
                for col in range(left_col, right_col + 1)
            ]
            copied_text += "\t".join(row_data) + "\n"

        QtWidgets.QApplication.clipboard().setText(copied_text)
        logger.debug("Selection copied to clipboard.")


class CommandTextEdit(QtWidgets.QTextEdit):
    """
    QTextEdit with prompt prefix and returnPressed signal for command input.
    """
    return_pressed = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.prompt = ''

        self.setStyleSheet('QTextEdit {border: none; padding: 5px;}')

        self.prompt_format = QtGui.QTextCharFormat()
        self.prompt_format.setForeground(QtGui.QBrush(QtGui.QColor("#008000")))
        self.prompt_format.setFontWeight(QtGui.QFont.Bold)
        self.default_format = QtGui.QTextCharFormat()

    def set_prompt(self, prompt):
        """
        Sets the prompt text and resets the input field.
        """
        logger.debug(f"Setting prompt: {prompt}")
        self.clear()
        self.prompt = prompt

        cursor = self.textCursor()
        cursor.setCharFormat(self.prompt_format)
        cursor.insertText(self.prompt)
        cursor.setCharFormat(self.default_format)
        self.setTextCursor(cursor)

    def keyPressEvent(self, event):
        cursor = self.textCursor()

        if cursor.position() < len(self.prompt) and event.key() not in (
                QtCore.Qt.Key_Left, QtCore.Qt.Key_Right, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
            return

        if event.key() == QtCore.Qt.Key_Backspace and cursor.position() <= len(self.prompt):
            return

        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and not (
                event.modifiers() & QtCore.Qt.ShiftModifier):
            full_text = self.toPlainText()
            user_input = full_text[len(self.prompt):].strip()
            if user_input:
                logger.info(f"Command submitted: {user_input}")
                self.return_pressed.emit(user_input)
        else:
            super().keyPressEvent(event)

        cursor = self.textCursor()
        cursor.setCharFormat(self.default_format)
        self.setTextCursor(cursor)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._enforce_cursor_position()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self._enforce_cursor_position()

    def _enforce_cursor_position(self):
        """
        Ensures the cursor does not move before the prompt.
        """
        cursor = self.textCursor()
        if cursor.position() < len(self.prompt):
            cursor.setPosition(len(self.prompt))
            self.setTextCursor(cursor)
            cursor.setCharFormat(self.default_format)
            self.setTextCursor(cursor)


class Form(QtWidgets.QWidget, Ui_Form):
    """
    UI Form class.

    """

    def __init__(self, parent=None, **kwargs):
        """
        Initialize the UI form.

        Args:
            parent (QWidget): Parent widget.
            **kwargs: Additional arguments for customization or metadata.
        """
        super().__init__(parent)
        self.kwargs = kwargs
        self.session = kwargs.get("session")
        self.setup_ui(self)
        self.connect_button.clicked.connect(self.connect)

    def connect(self):
        """
        Initiates connections for each device entered in the input field.
        Adds a new tab for each device session.
        """
        device_list = self.device_input.text().split(',')
        for device in device_list:
            device = device.strip()
            if device:
                self.sessions_tab_widget.add_session(device)
        self.device_input.clear()
