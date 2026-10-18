import re
import shutil
import sys
from pathlib import Path
from PySide6.QtCore import QDir, QProcess, Qt, QSettings
from PySide6.QtGui import QFont, QPixmap, QAction
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFileSystemModel,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QMenu,
    QLineEdit,
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
TEXT_EXTENSIONS = {
    ".py", ".txt", ".json", ".xml", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".md", ".csv", ".html", ".css", ".js", ".glsl", ".vert", ".frag",
}


def create_sprite_script(sprite_name, image_name):
    """Return a starter behavior script for a sprite package."""
    return f"""from pathlib import Path

SPRITE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = SPRITE_DIR / "assets"
IMAGE_PATH = ASSETS_DIR / {image_name!r}


class Sprite:
    # Behavior module for the {sprite_name} sprite.

    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y
        self.visible = True

    def update(self, dt):
        # Called every frame; dt is elapsed time in seconds.
        pass

    def on_collision(self, other):
        # Called when this sprite collides with another sprite.
        pass
"""

class Editor(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(
            "PyGameEngine"
        )
        self.setWindowTitle("PyGame Engine — Sprite Editor")
        self.resize(1200, 760)
        self.setAcceptDrops(True)

        self.project_dir = None
        self.current_file = None
        self.current_game_file = None
        self.game_process = QProcess(self)
        self.game_process.finished.connect(self.game_finished)
        self.game_process.errorOccurred.connect(self.game_error)
        # Game console output
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setMaximumBlockCount(5000)
        self.console_output.setFont(QFont("Monospace", 10))
        self.console_output.setPlaceholderText("Game output...")

        # Command input
        self.console_input = QLineEdit()
        self.console_input.setFont(QFont("Monospace", 10))
        self.console_input.setPlaceholderText("Enter input for the game...")
        self.console_input.returnPressed.connect(self.send_console_input)

        self.game_process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self.game_process.readyReadStandardOutput.connect(
            self.read_game_output
        )

        self.game_process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self.game_process.readyReadStandardOutput.connect(
            self.read_game_output
        )

        # Asset browser
        self.asset_list = QListWidget()
        self.asset_list.itemDoubleClicked.connect(self.prompt_create_selected)
        self.refresh_button = QPushButton("Refresh Assets")
        self.refresh_button.clicked.connect(self.scan_assets)
        self.create_button = QPushButton("Create Sprite")
        self.create_button.clicked.connect(self.prompt_create_selected)
        self.status = QLabel("Select a project directory to begin.")
        self.status.setWordWrap(True)

        sidebar = QVBoxLayout()
        sidebar.addWidget(QLabel("Asset Browser"))
        sidebar.addWidget(self.asset_list, 1)
        sidebar.addWidget(self.refresh_button)
        sidebar.addWidget(self.create_button)
        sidebar.addWidget(self.status)

        # Stage
        self.scene = QGraphicsScene(self)
        self.stage = QGraphicsView(self.scene)
        self.stage.setBackgroundBrush(Qt.GlobalColor.darkGray)
        self.stage.setAcceptDrops(True)

        # Sprite file browser
        self.file_model = None
        self.file_tree = QTreeView()
        self.file_tree.setColumnWidth(0, 220)
        for column in range(1, 4):
            self.file_tree.hideColumn(column)
        self.file_editor = QPlainTextEdit()
        self.file_editor.setFont(QFont("Monospace", 10))
        self.file_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.image_preview = QLabel("Select an image to preview")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setMinimumSize(200, 200)
        self.file_info = QLabel("Select a file to view it.")
        self.file_info.setWordWrap(True)

        self.file_stack = QStackedWidget()
        self.file_stack.addWidget(self.file_editor)
        self.file_stack.addWidget(self.image_preview)
        self.file_stack.addWidget(self.file_info)
        self.file_path_label = QLabel("No file selected")
        self.file_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.save_file_button = QPushButton("Save File")
        self.save_file_button.clicked.connect(self.save_sprite_file)
        self.save_file_button.setEnabled(False)

        sprite_panel = QWidget()
        sprite_layout = QVBoxLayout(sprite_panel)
        sprite_layout.addWidget(self.file_path_label)
        sprite_layout.addWidget(self.file_stack, 1)
        sprite_layout.addWidget(self.save_file_button)
        self.new_sprite_file_button = QPushButton("+ New File")
        self.new_sprite_file_button.clicked.connect(self.create_sprite_file)
        self.new_sprite_folder_button = QPushButton("+ New Folder")
        self.new_sprite_folder_button.clicked.connect(self.create_sprite_folder)
        sprite_buttons = QHBoxLayout()
        sprite_buttons.addWidget(self.new_sprite_file_button)
        sprite_buttons.addWidget(self.new_sprite_folder_button)
        sprite_layout.addLayout(sprite_buttons)

        self.file_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.file_splitter.addWidget(self.file_tree)
        self.file_splitter.addWidget(sprite_panel)
        self.file_splitter.setStretchFactor(1, 1)

        # Game file browser/editor
        self.game_file_tree = QTreeWidget()
        self.game_file_tree.setHeaderLabel("Game Project")
        self.game_file_tree.itemClicked.connect(self.open_game_file)
        self.game_file_editor = QPlainTextEdit()
        self.game_file_editor.setFont(QFont("Monospace", 10))
        self.game_file_editor.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.NoWrap
        )
        self.game_image_preview = QLabel("Select an asset to preview")
        self.game_image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.game_file_info = QLabel("Select a file to view or edit.")
        self.game_file_info.setWordWrap(True)
        self.game_file_stack = QStackedWidget()
        self.game_file_stack.addWidget(self.game_file_editor)
        self.game_file_stack.addWidget(self.game_image_preview)
        self.game_file_stack.addWidget(self.game_file_info)
        self.game_file_path_label = QLabel("No file selected")
        self.game_file_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.game_save_button = QPushButton("Save Game File")
        self.game_save_button.clicked.connect(self.save_game_file)
        self.game_save_button.setEnabled(False)

        game_panel = QWidget()
        game_layout = QVBoxLayout(game_panel)
        game_layout.addWidget(self.game_file_path_label)
        game_layout.addWidget(self.game_file_stack, 1)
        game_layout.addWidget(self.game_save_button)
        self.new_game_file_button = QPushButton("+ New File")
        self.new_game_file_button.clicked.connect(self.create_game_file)
        self.new_game_folder_button = QPushButton("+ New Folder")
        self.new_game_folder_button.clicked.connect(self.create_game_folder)
        game_buttons = QHBoxLayout()
        game_buttons.addWidget(self.new_game_file_button)
        game_buttons.addWidget(self.new_game_folder_button)
        game_layout.addLayout(game_buttons)

        self.game_file_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.game_file_splitter.addWidget(self.game_file_tree)
        self.game_file_splitter.addWidget(game_panel)
        self.game_file_splitter.setStretchFactor(1, 1)

        self.editor_tabs = QTabWidget()
        self.editor_tabs.addTab(self.stage, "Stage")
        self.editor_tabs.addTab(self.file_splitter, "Sprite Files")
        self.editor_tabs.addTab(self.game_file_splitter, "Game Files")

        # Sprite file browser context menu
        self.file_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.file_tree.customContextMenuRequested.connect(
            self.show_sprite_context_menu
        )

        # Game file browser context menu
        self.game_file_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.game_file_tree.customContextMenuRequested.connect(
            self.show_game_context_menu
        )
        # Toolbar and overall layout
        self.project_label = QLabel("Project: (none)")
        self.project_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.stage.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.stage.customContextMenuRequested.connect(
            self.show_stage_context_menu
        )
        self.select_project_button = QPushButton("Select Project")
        self.select_project_button.clicked.connect(self.select_project)
        self.new_project_button = QPushButton("New Project")
        self.new_project_button.clicked.connect(self.create_project)

        self.run_button = QPushButton("▶  Run Game")
        self.run_button.clicked.connect(self.run_game)
        self.stop_button = QPushButton("■  Stop Game")
        self.stop_button.clicked.connect(self.stop_game)
        self.stop_button.hide()
        self.run_button.setEnabled(False)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("PyGame Engine"))
        toolbar.addWidget(self.project_label, 1)
        toolbar.addWidget(self.select_project_button)
        toolbar.addWidget(self.new_project_button)
        toolbar.addWidget(self.run_button)
        toolbar.addWidget(self.stop_button)

        content = QHBoxLayout()
        content.addLayout(sidebar, 1)
        content.addWidget(self.editor_tabs, 3)

        # Console panel
        console_panel = QWidget()
        console_layout = QVBoxLayout(console_panel)
        console_layout.setContentsMargins(0, 0, 0, 0)

        console_header = QHBoxLayout()
        console_header.addWidget(QLabel("Game Console"))
        console_header.addStretch()

        clear_console_button = QPushButton("Clear")
        clear_console_button.clicked.connect(self.console_output.clear)
        console_header.addWidget(clear_console_button)

        console_layout.addLayout(console_header)
        console_layout.addWidget(self.console_output, 1)
        console_layout.addWidget(self.console_input)
        console_panel.setMaximumHeight(220)
        console_panel.setMinimumHeight(120)

        # Main window layout
        root_layout = QVBoxLayout(self)
        root_layout.addLayout(toolbar)
        root_layout.addLayout(content, 1)
        root_layout.addWidget(console_panel)

        saved_path = self.settings.value("project_dir", "")

        if saved_path and Path(saved_path).is_dir():
            self.set_project(Path(saved_path), create_layout=False)
        else:
            self.set_project(
                Path(__file__).resolve().parent,
                create_layout=True
            )

    @property
    def asset_dir(self):
        return self.project_dir / "assets"

    @property
    def sprite_dir(self):
        return self.project_dir / "sprites"

    def set_project(self, directory, create_layout=True):
        """Switch the editor's active project and refresh every project view."""
        directory = Path(directory).expanduser().resolve()
        if not directory.is_dir():
            QMessageBox.warning(self, "Invalid project", "Choose an existing directory.")
            return

        self.project_dir = directory
        self.settings.setValue("project_dir", str(directory))
        if create_layout:
            try:
                self.asset_dir.mkdir(parents=True, exist_ok=True)
                self.sprite_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                QMessageBox.critical(
                    self, "Project setup failed",
                    f"Could not prepare the project directory:\n{exc}"
                )
                return

        self.project_label.setText(f"Project: {directory}")
        self.setWindowTitle(f"PyGame Engine — {directory.name}")
        self.current_file = None
        self.current_game_file = None
        self.file_path_label.setText("No file selected")
        self.game_file_path_label.setText("No file selected")
        self.save_file_button.setEnabled(False)
        self.game_save_button.setEnabled(False)
        self.file_editor.clear()
        self.game_file_editor.clear()
        self.scan_assets()
        self.refresh_sprite_files()
        self.refresh_game_files()
        self.run_button.setEnabled(True)
        self.status.setText(f"Project loaded: {directory}")

    def select_project(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Project Directory",
            str(self.project_dir or Path.home())
        )
        if directory:
            self.set_project(directory)

    def create_project(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Choose Parent Directory for New Project",
            str(self.project_dir or Path.home())
        )
        if not directory:
            return
        name, accepted = QInputDialog.getText(
            self, "New Project", "Project folder name:"
        )
        if not accepted:
            return
        name = name.strip()
        if (not name or name in {".", ".."} or "/" in name
                or "\\" in name or "\0" in name):
            QMessageBox.warning(self, "Invalid name", "Enter a valid folder name.")
            return
        target = Path(directory) / name
        try:
            target.mkdir(parents=False, exist_ok=False)
            (target / "assets").mkdir()
            (target / "sprites").mkdir()
        except FileExistsError:
            QMessageBox.warning(
                self, "Already exists", f"This project already exists:\n{target}"
            )
            return
        except OSError as exc:
            QMessageBox.critical(
                self, "Project creation failed",
                f"Could not create the project:\n{exc}"
            )
            return
        self.set_project(target)

    def scan_assets(self):
        self.asset_list.clear()
        if not self.project_dir or not self.asset_dir.is_dir():
            return
        for path in sorted(self.asset_dir.rglob("*")):
            if path.is_symlink():
                continue
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                self.asset_list.addItem(str(path.relative_to(self.asset_dir)))

    def refresh_sprite_files(self):
        if not self.project_dir:
            return
        old_model = self.file_model
        self.file_model = QFileSystemModel(self)
        self.file_model.setFilter(
            QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot
        )
        self.file_model.setRootPath(str(self.sprite_dir))
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIndex(self.file_model.index(str(self.sprite_dir)))
        self.file_tree.selectionModel().currentChanged.connect(
            self.open_sprite_file
        )
        if old_model is not None:
            old_model.deleteLater()

    def refresh_game_files(self):
        self.game_file_tree.clear()
        if not self.project_dir:
            return
        root_item = QTreeWidgetItem([self.project_dir.name + "/"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(self.project_dir))
        self.game_file_tree.addTopLevelItem(root_item)
        self._populate_game_tree(root_item, self.project_dir)
        root_item.setExpanded(True)
        self.game_file_tree.expandToDepth(1)

    def _populate_game_tree(self, parent_item, directory):
        try:
            entries = sorted(
                directory.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except OSError:
            return
        for path in entries:
            # Keep the editor's own source and Python cache out of the project view.
            if path.name == "__pycache__" or path.is_symlink():
                continue
            if path.is_dir():
                child = QTreeWidgetItem([path.name + "/"])
                child.setData(0, Qt.ItemDataRole.UserRole, str(path))
                parent_item.addChild(child)
                self._populate_game_tree(child, path)
            elif path.is_file():
                child = QTreeWidgetItem([path.name])
                child.setData(0, Qt.ItemDataRole.UserRole, str(path))
                parent_item.addChild(child)

    def _inside(self, path, root):
        try:
            Path(path).resolve().relative_to(Path(root).resolve())
            return True
        except ValueError:
            return False

    def prompt_create_selected(self, item=None):
        # QPushButton.clicked may pass a bool rather than a list item.
        if not hasattr(item, "text"):
            item = self.asset_list.currentItem()
        if item is None:
            QMessageBox.information(
                self, "No image selected",
                "Select an image in the asset browser first."
            )
            return
        source = (self.asset_dir / item.text()).resolve()
        if not self._inside(source, self.asset_dir) or not source.is_file():
            return
        self.ask_sprite_name(source)

    def ask_sprite_name(self, source):
        name, accepted = QInputDialog.getText(
            self, "Create Sprite", "Sprite name:", text=source.stem
        )
        if accepted:
            self.create_sprite(source, name)

    def create_sprite(self, source, name):
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_-")
        if not name:
            QMessageBox.warning(
                self, "Invalid name", "Enter a name containing letters or numbers."
            )
            return
        source = Path(source).resolve()
        if (not source.is_file()
                or source.suffix.lower() not in IMAGE_EXTENSIONS):
            QMessageBox.warning(
                self, "Invalid image", "The selected file is not a supported image."
            )
            return
        destination = self.sprite_dir / name
        if destination.exists():
            QMessageBox.warning(
                self, "Sprite already exists",
                f"A sprite named '{name}' already exists."
            )
            return
        try:
            sprite_assets = destination / "assets"
            sprite_scripts = destination / "scripts"
            sprite_assets.mkdir(parents=True)
            sprite_scripts.mkdir()
            shutil.copy2(source, sprite_assets / source.name)
            (sprite_scripts / "main.py").write_text(
                create_sprite_script(name, source.name), encoding="utf-8"
            )
        except OSError as exc:
            shutil.rmtree(destination, ignore_errors=True)
            QMessageBox.critical(
                self, "Import failed", f"Could not create sprite:\n{exc}"
            )
            return
        self.add_to_stage(sprite_assets / source.name)
        self.status.setText(f"Created sprite: {name}")
        self.scan_assets()
        self.refresh_sprite_files()
        self.refresh_game_files()

    def add_to_stage(self, image_path):
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            QMessageBox.warning(
                self, "Preview failed", f"Could not preview image:\n{image_path}"
            )
            return
        sprite = QGraphicsPixmapItem(pixmap)
        sprite.setData(0, str(image_path))
        self.scene.addItem(sprite)
        self.stage.setSceneRect(self.scene.itemsBoundingRect())
        self.stage.centerOn(sprite)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(
            Path(url.toLocalFile()).suffix.lower() in IMAGE_EXTENSIONS
            for url in event.mimeData().urls() if url.isLocalFile()
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                # Dropped images outside the project are copied into assets first.
                try:
                    self.asset_dir.mkdir(parents=True, exist_ok=True)
                    destination = self.asset_dir / path.name
                    if path.resolve() != destination.resolve():
                        if destination.exists():
                            QMessageBox.warning(
                                self, "Asset already exists",
                                f"An asset named '{path.name}' already exists in assets/."
                            )
                            return
                        shutil.copy2(path, destination)
                except OSError as exc:
                    QMessageBox.critical(
                        self, "Import failed", f"Could not import image:\n{exc}"
                    )
                    return
                self.scan_assets()
                self.ask_sprite_name(destination)
                event.acceptProposedAction()
                return
        event.ignore()

    def open_sprite_file(self, index, previous_index=None):
        if not index.isValid() or not self.file_model:
            return
        path = Path(self.file_model.filePath(index)).resolve()
        if not self._inside(path, self.sprite_dir):
            return
        if not path.is_file():
            self.current_file = None
            self.file_path_label.setText(str(path))
            self.file_stack.setCurrentIndex(2)
            self.file_info.setText("Select a file to view or edit.")
            self.save_file_button.setEnabled(False)
            return
        self.current_file = path
        self.file_path_label.setText(str(path.relative_to(self.sprite_dir)))
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                self.file_stack.setCurrentIndex(2)
                self.file_info.setText("Unable to preview this image.")
            else:
                self.image_preview.setPixmap(pixmap.scaled(
                    700, 600, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
                self.file_stack.setCurrentIndex(1)
            self.save_file_button.setEnabled(False)
            return
        if path.suffix.lower() in TEXT_EXTENSIONS:
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                self.file_stack.setCurrentIndex(2)
                self.file_info.setText(f"Cannot read file:\n{exc}")
                self.save_file_button.setEnabled(False)
                return
            self.file_editor.setPlainText(content)
            self.file_stack.setCurrentIndex(0)
            self.save_file_button.setEnabled(True)
            return
        self.file_stack.setCurrentIndex(2)
        self.file_info.setText(
            f"Preview or editing is not supported for:\n{path.name}\n\n"
            "Use a specialized editor for binary files."
        )
        self.save_file_button.setEnabled(False)

    def save_sprite_file(self):
        if self.current_file is None:
            return
        if not self._inside(self.current_file, self.sprite_dir):
            QMessageBox.warning(self, "Invalid path", "File is outside sprites/.")
            return
        try:
            self.current_file.write_text(
                self.file_editor.toPlainText(), encoding="utf-8"
            )
            self.status.setText(f"Saved: {self.current_file.name}")
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", f"Could not save file:\n{exc}")

    def open_game_file(self, item, column=0):
        raw_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not raw_path:
            return
        path = Path(raw_path).resolve()
        if not self._inside(path, self.project_dir):
            return
        if not path.is_file():
            self.current_game_file = None
            self.game_file_path_label.setText(str(path.relative_to(self.project_dir)))
            self.game_file_stack.setCurrentIndex(2)
            self.game_file_info.setText("Select a file inside this project.")
            self.game_save_button.setEnabled(False)
            return
        self.current_game_file = path
        self.game_file_path_label.setText(str(path.relative_to(self.project_dir)))
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                self.game_file_stack.setCurrentIndex(2)
                self.game_file_info.setText("Could not preview this image.")
            else:
                self.game_image_preview.setPixmap(pixmap.scaled(
                    800, 600, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
                self.game_file_stack.setCurrentIndex(1)
            self.game_save_button.setEnabled(False)
            return
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            self.game_file_stack.setCurrentIndex(2)
            self.game_file_info.setText(
                f"No text editor or preview for:\n{path.name}"
            )
            self.game_save_button.setEnabled(False)
            return
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self.game_file_stack.setCurrentIndex(2)
            self.game_file_info.setText(f"Could not read file:\n{exc}")
            self.game_save_button.setEnabled(False)
            return
        self.game_file_editor.setPlainText(content)
        self.game_file_stack.setCurrentIndex(0)
        self.game_save_button.setEnabled(True)

    def save_game_file(self):
        if self.current_game_file is None:
            return
        if not self._inside(self.current_game_file, self.project_dir):
            QMessageBox.warning(self, "Invalid path", "File is outside the project.")
            return
        try:
            self.current_game_file.write_text(
                self.game_file_editor.toPlainText(), encoding="utf-8"
            )
            self.status.setText(f"Saved: {self.current_game_file.name}")
        except OSError as exc:
            QMessageBox.critical(
                self, "Save failed", f"Could not save the file:\n{exc}"
            )

    def read_game_output(self):
        output = bytes(
            self.game_process.readAllStandardOutput()
        ).decode("utf-8", errors="replace")

        if output:
            cursor = self.console_output.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(output)
            self.console_output.setTextCursor(cursor)
            self.console_output.ensureCursorVisible()

    def send_console_input(self):
        if (
            self.game_process.state()
            != QProcess.ProcessState.Running
        ):
            self.console_output.appendPlainText(
                "[No game is currently running]"
            )
            return

        command = self.console_input.text()
        self.console_input.clear()

        self.console_output.appendPlainText(f"> {command}")

        self.game_process.write(
            (command + "\n").encode("utf-8")
        )

    def run_game(self):
        game_path = self.project_dir / "game.py"
        if not game_path.is_file():
            QMessageBox.warning(
                self, "Game not found",
                f"Could not find:\n{game_path}\n\nCreate game.py in the project root first."
            )
            return
        if self.game_process.state() != QProcess.ProcessState.NotRunning:
            return
        self.console_output.clear()
        self.console_output.appendPlainText(
            f"> Starting game: {game_path.name}\n"
        )

        self.game_process.setWorkingDirectory(str(self.project_dir))
        self.game_process.setProgram(sys.executable)

        # -u disables Python's normal stdout/stderr buffering.
        self.game_process.setArguments(["-u", str(game_path)])
        self.game_process.start()
        if self.game_process.waitForStarted(2000):
            self.run_button.setEnabled(False)
            self.stop_button.show()
            self.status.setText("Game is running.")
        else:
            QMessageBox.critical(
                self, "Launch failed", self.game_process.errorString()
            )

    def stop_game(self):
        if self.game_process.state() == QProcess.ProcessState.NotRunning:
            return
        self.game_process.terminate()
        if not self.game_process.waitForFinished(1500):
            self.game_process.kill()

    def game_finished(self, exit_code, exit_status):
        self.run_button.setEnabled(True)
        self.stop_button.hide()

        if exit_status == QProcess.ExitStatus.NormalExit:
            self.status.setText(f"Game exited (code {exit_code}).")
            self.console_output.appendPlainText(
                f"\n[Game exited with code {exit_code}]"
            )
        else:
            self.status.setText("Game process stopped.")
            self.console_output.appendPlainText(
                "\n[Game process stopped]"
            )

    def game_error(self, error):
        message = self.game_process.errorString()

        self.console_output.appendPlainText(
            f"\n[Process error] {message}"
        )

        if error == QProcess.ProcessError.FailedToStart:
            self.run_button.setEnabled(True)
            self.stop_button.hide()
            self.status.setText(f"Could not launch game: {message}")

    def show_sprite_context_menu(self, position):
        index = self.file_tree.indexAt(position)

        if index.isValid():
            self.file_tree.setCurrentIndex(index)
            selected = Path(self.file_model.filePath(index)).resolve()
            target = selected if selected.is_dir() else selected.parent
        else:
            target = self.sprite_dir
            selected = None

        menu = QMenu(self)

        new_file = menu.addAction("New File")
        new_folder = menu.addAction("New Folder")
        menu.addSeparator()
        rename = menu.addAction("Rename")
        delete = menu.addAction("Delete")
        menu.addSeparator()
        refresh = menu.addAction("Refresh")

        rename.setEnabled(selected is not None)
        delete.setEnabled(selected is not None)

        action = menu.exec(
            self.file_tree.viewport().mapToGlobal(position)
        )

        if action == new_file:
            self.create_item_in_directory(
                target, allowed_root=self.sprite_dir
            )
            self.refresh_sprite_files()

        elif action == new_folder:
            self.create_item_in_directory(
                target, is_folder=True,
                allowed_root=self.sprite_dir
            )
            self.refresh_sprite_files()

        elif action == rename and selected is not None:
            self.rename_project_item(selected, self.sprite_dir)
            self.refresh_sprite_files()

        elif action == delete and selected is not None:
            self.delete_project_item(selected, self.sprite_dir)
            self.refresh_sprite_files()

        elif action == refresh:
            self.refresh_sprite_files()


    def show_game_context_menu(self, position):
        item = self.game_file_tree.itemAt(position)

        if item:
            self.game_file_tree.setCurrentItem(item)
            raw_path = item.data(0, Qt.ItemDataRole.UserRole)
            selected = Path(raw_path).resolve() if raw_path else None
            target = (
                selected if selected and selected.is_dir()
                else selected.parent if selected else self.project_dir
            )
        else:
            selected = None
            target = self.project_dir

        menu = QMenu(self)

        new_file = menu.addAction("New File")
        new_folder = menu.addAction("New Folder")
        menu.addSeparator()
        rename = menu.addAction("Rename")
        delete = menu.addAction("Delete")
        menu.addSeparator()
        refresh = menu.addAction("Refresh")

        # Never allow renaming or deleting the project root.
        can_modify = (
            selected is not None
            and selected != self.project_dir.resolve()
            and self._inside(selected, self.project_dir)
        )
        rename.setEnabled(can_modify)
        delete.setEnabled(can_modify)

        action = menu.exec(
            self.game_file_tree.viewport().mapToGlobal(position)
        )

        if action == new_file:
            self.create_item_in_directory(
                target, allowed_root=self.project_dir
            )
            self.refresh_game_files()

        elif action == new_folder:
            self.create_item_in_directory(
                target, is_folder=True,
                allowed_root=self.project_dir
            )
            self.refresh_game_files()

        elif action == rename and can_modify:
            self.rename_project_item(selected, self.project_dir)
            self.refresh_game_files()

        elif action == delete and can_modify:
            self.delete_project_item(selected, self.project_dir)
            self.refresh_game_files()

        elif action == refresh:
            self.refresh_game_files()


    def rename_project_item(self, path, allowed_root):
        path = Path(path).resolve()
        root = Path(allowed_root).resolve()

        if path == root or not self._inside(path, root):
            QMessageBox.warning(
                self, "Invalid path",
                "This item cannot be renamed."
            )
            return

        name, accepted = QInputDialog.getText(
            self, "Rename", "New name:", text=path.name
        )

        if not accepted:
            return

        name = name.strip()

        if (
            not name or name in {".", ".."}
            or "/" in name or "\\" in name or "\0" in name
        ):
            QMessageBox.warning(
                self, "Invalid name", "Enter a valid name."
            )
            return

        destination = path.parent / name

        if destination.exists():
            QMessageBox.warning(
                self, "Already exists",
                f"This item already exists:\n{destination}"
            )
            return

        try:
            path.rename(destination)
            self.status.setText(f"Renamed to: {name}")
        except OSError as exc:
            QMessageBox.critical(
                self, "Rename failed", str(exc)
            )


    def delete_project_item(self, path, allowed_root):
        path = Path(path).resolve()
        root = Path(allowed_root).resolve()

        if path == root or not self._inside(path, root):
            QMessageBox.warning(
                self, "Invalid path",
                "This item cannot be deleted."
            )
            return

        answer = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete this item?\n\n{path.name}\n\n"
            "Folders and their contents will also be deleted.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

            self.status.setText(f"Deleted: {path.name}")

        except OSError as exc:
            QMessageBox.critical(
                self, "Delete failed", str(exc)
            )

    def create_item_in_directory(self, base_dir, is_folder=False, allowed_root=None):
        base_dir = Path(base_dir).resolve()
        if allowed_root is not None and not self._inside(base_dir, allowed_root):
            QMessageBox.warning(
                self, "Invalid location",
                f"Items can only be created inside:\n{allowed_root}"
            )
            return
        if not base_dir.is_dir():
            QMessageBox.warning(
                self, "Invalid location", "The selected location is not a directory."
            )
            return
        name, accepted = QInputDialog.getText(
            self, "Create Folder" if is_folder else "Create File",
            "Folder name:" if is_folder else "File name:"
        )
        if not accepted:
            return
        name = name.strip()
        if (not name or name in {".", ".."} or "/" in name
                or "\\" in name or "\0" in name):
            QMessageBox.warning(
                self, "Invalid name",
                "Enter a valid name without directory separators."
            )
            return
        target = base_dir / name
        if target.exists():
            QMessageBox.warning(
                self, "Already exists", f"This path already exists:\n{target}"
            )
            return
        try:
            if is_folder:
                target.mkdir()
            else:
                target.touch(exist_ok=False)
        except OSError as exc:
            QMessageBox.critical(
                self, "Creation failed", f"Could not create the item:\n{exc}"
            )
            return
        self.status.setText(f"Created: {target.name}")

    def show_stage_context_menu(self, position):
        menu = QMenu(self)

        add_sprite = menu.addAction("Add Sprite from Assets")
        menu.addSeparator()
        fit = menu.addAction("Fit Contents")
        clear = menu.addAction("Clear Stage")

        action = menu.exec(
            self.stage.viewport().mapToGlobal(position)
        )

        if action == add_sprite:
            self.prompt_create_selected()

        elif action == fit:
            self.stage.fitInView(
                self.scene.itemsBoundingRect(),
                Qt.AspectRatioMode.KeepAspectRatio
            )

        elif action == clear:
            answer = QMessageBox.question(
                self, "Clear Stage",
                "Remove all items from the stage?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            )

            if answer == QMessageBox.StandardButton.Yes:
                self.scene.clear()

    def _selected_sprite_directory(self):
        index = self.file_tree.currentIndex()
        if index.isValid():
            selected = Path(self.file_model.filePath(index)).resolve()
            base = selected if selected.is_dir() else selected.parent
        else:
            base = self.sprite_dir
        return base

    def create_sprite_file(self):
        self.create_item_in_directory(
            self._selected_sprite_directory(), allowed_root=self.sprite_dir
        )
        self.refresh_sprite_files()

    def create_sprite_folder(self):
        self.create_item_in_directory(
            self._selected_sprite_directory(), is_folder=True,
            allowed_root=self.sprite_dir
        )
        self.refresh_sprite_files()

    def _selected_game_directory(self):
        item = self.game_file_tree.currentItem()
        raw_path = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        selected = Path(raw_path).resolve() if raw_path else self.project_dir
        return selected if selected.is_dir() else selected.parent

    def create_game_file(self):
        self.create_item_in_directory(
            self._selected_game_directory(), allowed_root=self.project_dir
        )
        self.refresh_game_files()

    def create_game_folder(self):
        self.create_item_in_directory(
            self._selected_game_directory(), is_folder=True,
            allowed_root=self.project_dir
        )
        self.refresh_game_files()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = Editor()
    editor.show()
    sys.exit(app.exec())

