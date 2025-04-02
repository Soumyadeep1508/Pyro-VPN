import sys
import os
import shutil
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QListWidget, QPushButton, QTextEdit,
    QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QGroupBox, QFormLayout,
    QInputDialog, QMessageBox, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QProcess, QObject
from PyQt5.QtNetwork import QTcpSocket
from PyQt5.QtGui import QFont

# Configuration Manager: Handles importing and listing OpenVPN configs
class ConfigManager:
    def __init__(self):
        super().__init__()
        self.config_dir = os.path.expanduser('~/.openvpn-gui/configs')
        os.makedirs(self.config_dir, exist_ok=True)

    def import_config(self, ovpn_path):
        """Import an .ovpn file and its referenced files."""
        config_name = os.path.basename(ovpn_path).replace('.ovpn', '')
        config_subdir = os.path.join(self.config_dir, config_name)
        os.makedirs(config_subdir, exist_ok=True)
        dest_ovpn = os.path.join(config_subdir, os.path.basename(ovpn_path))
        shutil.copy(ovpn_path, dest_ovpn)
        # Copy any referenced files (e.g., certificates)
        with open(ovpn_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith(('ca ', 'cert ', 'key ', 'tls-auth ', 'tls-crypt ')):
                    parts = line.split()
                    if len(parts) > 1:
                        file_path = parts[1]
                        if not os.path.isabs(file_path):
                            file_path = os.path.join(os.path.dirname(ovpn_path), file_path)
                        if os.path.exists(file_path):
                            shutil.copy(file_path, config_subdir)
        return config_name

    def list_configs(self):
        """Return a list of available config names."""
        return [d for d in os.listdir(self.config_dir) if os.path.isdir(os.path.join(self.config_dir, d))]

# OpenVPN Controller: Manages the OpenVPN process and socket communication
class OpenVPNController(QObject):
    state_changed = pyqtSignal(str, dict)
    log_message = pyqtSignal(str)
    auth_required = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.process = QProcess()
        self.socket = QTcpSocket()
        self.buffer = b''
        self.current_state = 'DISCONNECTED'
        self.details = {}

    def start_openvpn(self, config_path):
        """Start OpenVPN with the given config and connect to its management socket."""
        self.process.start('pkexec', ['openvpn', '--config', config_path, '--management', '127.0.0.1', '7505'])
        self.process.waitForStarted(2000)
        self.socket.connectToHost('127.0.0.1', 7505)
        if self.socket.waitForConnected(2000):
            self.socket.readyRead.connect(self.on_ready_read)
            self.send_command('state on')
            self.send_command('log on')
            self.send_command('hold release')
        else:
            self.log_message.emit("Error: Could not connect to OpenVPN management socket.")

    def disconnect(self):
        """Disconnect the VPN by sending SIGTERM."""
        self.send_command('signal SIGTERM')
        self.process.waitForFinished(2000)
        self.socket.disconnectFromHost()

    def send_command(self, command):
        """Send a command to the OpenVPN management socket."""
        if self.socket.state() == QTcpSocket.ConnectedState:
            self.socket.write((command + '\n').encode('utf-8'))

    @pyqtSlot()
    def on_ready_read(self):
        """Process incoming data from the management socket."""
        data = self.socket.readAll()
        self.buffer += data
        lines = self.buffer.split(b'\n')
        self.buffer = lines.pop()
        for line in lines:
            self.process_line(line.decode('utf-8').strip())

    def process_line(self, line):
        """Parse management socket messages and emit signals."""
        if line.startswith('>STATE:'):
            parts = line[7:].split(',')
            state = parts[1]
            self.current_state = state
            if state == 'CONNECTED':
                self.details = {'remote_ip': parts[4], 'local_ip': parts[3]}
            else:
                self.details = {}
            self.state_changed.emit(state, self.details)
        elif line.startswith('>LOG:'):
            log_message = line.split(',', 2)[2]
            self.log_message.emit(log_message)
        elif line.startswith('>PASSWORD:'):
            self.auth_required.emit()

# Main Window: The GUI with a vintage hacker aesthetic
class MainWindow(QMainWindow):
    connect_signal = pyqtSignal(str)
    disconnect_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenVPN Client")
        self.setGeometry(100, 100, 800, 600)
        self.config_manager = ConfigManager()
        self.openvpn_controller = OpenVPNController()
        self.setup_ui()
        self.load_configs()
        self.connect_signals()

    def setup_ui(self):
        """Set up the UI components with a retro style."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        self.setStyleSheet("background-color: black;")

        # Title
        self.title_label = QLabel("OpenVPN Client")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #00ff00; font-family: 'VT323'; font-size: 24px;")
        main_layout.addWidget(self.title_label)

        # Main content layout
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        # Config list
        self.config_list = QListWidget()
        self.config_list.setStyleSheet(
            "background-color: #1a1a1a; color: #00ff00; border: 2px solid #00ff00; font-family: 'VT323'; font-size: 16px;"
        )
        content_layout.addWidget(self.config_list)

        # Buttons
        button_layout = QVBoxLayout()
        self.import_button = QPushButton("Import Config")
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        for btn in [self.import_button, self.connect_button, self.disconnect_button]:
            btn.setStyleSheet(
                "background-color: #1a1a1a; color: #00ff00; border: 2px solid #00ff00; font-family: 'VT323'; font-size: 16px;"
            )
            button_layout.addWidget(btn)
        content_layout.addLayout(button_layout)

        # Status box
        self.status_group = QGroupBox("Connection Status")
        self.status_group.setStyleSheet("color: #00ff00; font-family: 'VT323'; font-size: 14px;")
        form_layout = QFormLayout()
        self.status_label = QLabel("Disconnected")
        self.server_label = QLabel("N/A")
        self.ip_label = QLabel("N/A")
        form_layout.addRow("Status:", self.status_label)
        form_layout.addRow("Server:", self.server_label)
        form_layout.addRow("IP:", self.ip_label)
        self.status_group.setLayout(form_layout)
        content_layout.addWidget(self.status_group)

        # Log viewer
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet(
            "background-color: black; color: #00ff00; font-family: 'VT323'; font-size: 14px; border: 2px solid #00ff00;"
        )
        main_layout.addWidget(self.log_viewer)

    def load_configs(self):
        """Populate the config list with available configurations."""
        self.config_list.clear()
        configs = self.config_manager.list_configs()
        self.config_list.addItems(configs)

    @pyqtSlot()
    def on_import_clicked(self):
        """Handle importing a new config file."""
        ovpn_path, _ = QFileDialog.getOpenFileName(self, "Select OpenVPN Config", "", "OpenVPN Config (*.ovpn)")
        if ovpn_path:
            config_name = self.config_manager.import_config(ovpn_path)
            self.load_configs()
            QMessageBox.information(self, "Success", f"Configuration '{config_name}' imported successfully.")

    @pyqtSlot()
    def on_connect_clicked(self):
        """Start a VPN connection with the selected config."""
        selected_items = self.config_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Error", "Please select a configuration to connect.")
            return
        config_name = selected_items[0].text()
        config_path = os.path.join(self.config_manager.config_dir, config_name, f"{config_name}.ovpn")
        self.connect_signal.emit(config_path)

    @pyqtSlot()
    def on_disconnect_clicked(self):
        """Disconnect the active VPN connection."""
        self.disconnect_signal.emit()

    @pyqtSlot(str, dict)
    def update_status(self, state, details):
        """Update the status display based on OpenVPN state."""
        self.status_label.setText(state)
        if state == 'CONNECTED':
            self.server_label.setText(details.get('remote_ip', 'N/A'))
            self.ip_label.setText(details.get('local_ip', 'N/A'))
        else:
            self.server_label.setText('N/A')
            self.ip_label.setText('N/A')
        self.connect_button.setEnabled(state == 'DISCONNECTED')
        self.disconnect_button.setEnabled(state != 'DISCONNECTED')

    @pyqtSlot(str)
    def append_log(self, message):
        """Append a log message and auto-scroll if at bottom."""
        scroll_bar = self.log_viewer.verticalScrollBar()
        at_bottom = scroll_bar.value() == scroll_bar.maximum()
        self.log_viewer.append(message)
        if at_bottom:  # Ensure the scrollbar stays at the bottom if it was already there.
            scroll_bar.setValue(scroll_bar.maximum())

    @pyqtSlot()
    def on_auth_required(self):
        """Prompt for username and password when authentication is needed."""
        username, ok = QInputDialog.getText(self, "Authentication", "Username:")
        if not ok:
            return
        password, ok = QInputDialog.getText(self, "Authentication", "Password:", echo=QLineEdit.Password)
        if not ok:
            return
        self.openvpn_controller.send_command(f'username "Auth" {username}')
        self.openvpn_controller.send_command(f'password "Auth" {password}')

    def connect_signals(self):
        """Connect all signals to their slots."""
        self.import_button.clicked.connect(self.on_import_clicked)
        self.connect_button.clicked.connect(self.on_connect_clicked)
        self.disconnect_button.clicked.connect(self.on_disconnect_clicked)
        self.connect_signal.connect(self.openvpn_controller.start_openvpn)
        self.disconnect_signal.connect(self.openvpn_controller.disconnect)
        self.openvpn_controller.state_changed.connect(self.update_status)
        self.openvpn_controller.log_message.connect(self.append_log)
        self.openvpn_controller.auth_required.connect(self.on_auth_required)

# Run the application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())