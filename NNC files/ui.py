import sys
import threading
import time
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
                             QVBoxLayout, QWidget, QHeaderView, QMenu, QInputDialog, QMessageBox,
                             QSystemTrayIcon, QStyle, QFileDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer, QThread
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor, QCursor, QBrush, QPixmap

from monitor import HardwareMonitor
from alerts import AlertManager

class WorkerSignals(QObject):
    data_updated = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

class MonitorWorker(QThread):
    def __init__(self, monitor, signals):
        super().__init__()
        self.monitor = monitor
        self.signals = signals
        self.running = True

    def run(self):
        import logging
        logging.info("Worker thread started")
        while self.running:
            try:
                logging.debug("Worker requesting data...")
                data = self.monitor.get_data()
                logging.debug("Worker received data, emitting signal")
                self.signals.data_updated.emit(data)
            except Exception as e:
                logging.error(f"Worker error: {e}", exc_info=True)
                self.signals.error_occurred.emit(str(e))
            time.sleep(2) # Update every 2 seconds
        logging.info("Worker thread stopped")

    def stop(self):
        self.running = False

class ReorderableTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)

    def dragMoveEvent(self, event):
        # Default handling first to calculate drop indicator
        super().dragMoveEvent(event)
        
        # Get the item being dragged (source)
        # Assuming single selection or all from same level for simplicity
        selected_items = self.selectedItems()
        if not selected_items:
            event.ignore()
            return
            
        source_item = selected_items[0]
        
        # Get the item under the mouse (target)
        target_item = self.itemAt(event.position().toPoint())
        
        if not target_item:
            # Dropping in empty space. 
            # Only allow if source is top-level (parent is None)
            if source_item.parent() is None:
                event.accept()
            else:
                event.ignore()
            return

        # Rule 1: Must share the same parent (Siblings only)
        if source_item.parent() != target_item.parent():
            event.ignore()
            return

        # Rule 2: No dropping ON an item (Nesting), only Above or Below
        # QAbstractItemView.DropIndicatorPosition.OnItem = 0
        if self.dropIndicatorPosition() == QTreeWidget.DropIndicatorPosition.OnItem:
            event.ignore()
            return
            
        event.accept()

    def dropEvent(self, event):
        # Double check logic in dropEvent to be safe
        selected_items = self.selectedItems()
        if not selected_items:
            event.ignore()
            return
            
        source_item = selected_items[0]
        target_item = self.itemAt(event.position().toPoint())
        
        if target_item:
            if source_item.parent() != target_item.parent():
                event.ignore()
                return
            if self.dropIndicatorPosition() == QTreeWidget.DropIndicatorPosition.OnItem:
                event.ignore()
                return
        elif source_item.parent() is not None:
             # Prevent dropping child into empty space (becoming root)
             event.ignore()
             return

        super().dropEvent(event)


class HWMonitorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nick's Nerve Center")
        self.resize(600, 800)
        
        # Set Window Icon
        if getattr(sys, 'frozen', False):
            icon_path = os.path.join(sys._MEIPASS, 'NNC.ico')
        else:
            # ui.py is in hwmonitor-clone/, icon is in same dir
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'NNC.ico')
            
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        import logging
        logging.info("Initializing HWMonitorWindow")
        
        # White background styling
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("white"))
        palette.setColor(QPalette.ColorRole.Base, QColor("white"))
        palette.setColor(QPalette.ColorRole.Text, QColor("black"))
        self.setPalette(palette)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.tree = ReorderableTreeWidget()
        self.tree.setHeaderLabels(["Sensor", "Value", "Min", "Max"])
        # Fix Header Resizing: Use Interactive to allow user resizing, or Stretch for the first column but allow others to be resized
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive) 
        self.tree.header().setStretchLastSection(False)
        self.tree.header().resizeSection(0, 300) # Give sensor name more space by default
        
        self.tree.setAlternatingRowColors(True)
        
        # Drag and Drop setup moved to ReorderableTreeWidget class

        # Initial Style
        self.dark_mode = False
        self.background_image = None
        self.apply_style()

        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_menu)
        self.layout.addWidget(self.tree)

        # Main Menu
        menubar = self.menuBar()
        view_menu = menubar.addMenu('View')
        
        dark_mode_action = QAction('Toggle Dark Mode', self)
        dark_mode_action.triggered.connect(self.toggle_dark_mode)
        view_menu.addAction(dark_mode_action)
        
        bg_menu = menubar.addMenu('Background')
        set_bg_action = QAction('Set Custom Background (JPG)', self)
        set_bg_action.triggered.connect(self.set_custom_background)
        bg_menu.addAction(set_bg_action)
        
        clear_bg_action = QAction('Clear Background', self)
        clear_bg_action.triggered.connect(self.clear_background)
        bg_menu.addAction(clear_bg_action)

        self.monitor = HardwareMonitor()
        self.alert_manager = AlertManager()
        
        self.signals = WorkerSignals()
        self.signals.data_updated.connect(self.update_ui)
        self.signals.error_occurred.connect(self.show_error)

        self.worker = MonitorWorker(self.monitor, self.signals)
        self.worker.start()
        
        # Map to store tree items for updating
        self.items_map = {}

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.apply_style()
        
    def set_custom_background(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Open file', '.', "Image files (*.jpg *.jpeg)")
        if fname:
            self.background_image = fname
            self.apply_style()
            
    def clear_background(self):
        self.background_image = None
        self.apply_style()

    def apply_style(self):
        if self.background_image:
            # Custom Background Logic
            # Normalize path for CSS
            bg_path = self.background_image.replace('\\', '/')
            
            style = f"""
                QMainWindow {{
                    border-image: url("{bg_path}") 0 0 0 0 stretch stretch;
                }}
                QTreeWidget {{
                    background-color: rgba(255, 255, 255, 150); /* Semi-transparent white */
                    color: black;
                    border: none;
                    alternate-background-color: rgba(200, 200, 200, 150);
                }}
                QTreeWidget::item {{
                    padding: 5px;
                }}
                QTreeWidget::item:alternate {{
                    background-color: rgba(200, 200, 200, 150);
                }}
                QTreeWidget::item:selected {{
                    background-color: rgba(0, 120, 215, 100);
                    color: white;
                }}
                QMenuBar {{
                    background-color: rgba(255, 255, 255, 150);
                    color: black;
                }}
                QMenuBar::item {{
                    background-color: transparent;
                    color: black;
                }}
                QMenuBar::item:selected {{
                    background-color: rgba(0, 120, 215, 100);
                    color: white;
                }}
            """
            if self.dark_mode:
                 style += """
                    QTreeWidget {
                        background-color: rgba(0, 0, 0, 150); /* Semi-transparent black */
                        color: white;
                        alternate-background-color: rgba(50, 50, 50, 150);
                    }
                    QTreeWidget::item:alternate {
                        background-color: rgba(50, 50, 50, 150);
                    }
                    QMenuBar {
                        background-color: rgba(0, 0, 0, 150);
                        color: white;
                    }
                    QMenuBar::item {
                        color: white;
                    }
                 """
            self.setStyleSheet(style)
            self.tree.setStyleSheet(style) # Apply to tree specifically too
            
        elif self.dark_mode:
            # Dark Mode
            palette = self.palette()
            palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.ColorRole.Text, QColor("white"))
            self.setPalette(palette)
            
            self.setStyleSheet("""
                QMainWindow {
                    background-color: black;
                }
                QMenuBar {
                    background-color: #353535;
                    color: white;
                }
                QMenuBar::item {
                    background-color: transparent;
                    color: white;
                }
                QMenuBar::item:selected {
                    background-color: #0078d7;
                    color: white;
                }
            """)
            self.tree.setStyleSheet("""
                QTreeWidget {
                    background-color: #2b2b2b;
                    color: white;
                    border: none;
                    alternate-background-color: #323232;
                }
                QTreeWidget::item {
                    padding: 5px;
                }
                QTreeWidget::item:alternate {
                    background-color: #323232;
                }
                QTreeWidget::item:selected {
                    background-color: #0078d7;
                    color: white;
                }
                QHeaderView::section {
                    background-color: #353535;
                    color: white;
                }
            """)
        else:
            # Light Mode (Default)
            palette = self.palette()
            palette.setColor(QPalette.ColorRole.Window, QColor("white"))
            palette.setColor(QPalette.ColorRole.Base, QColor("white"))
            palette.setColor(QPalette.ColorRole.Text, QColor("black"))
            self.setPalette(palette)
            
            self.setStyleSheet("""
                QMenuBar {
                    background-color: #f0f0f0;
                    color: black;
                }
                QMenuBar::item {
                    background-color: transparent;
                    color: black;
                }
                QMenuBar::item:selected {
                    background-color: #e0e0e0;
                    color: black;
                }
            """)
            self.tree.setStyleSheet("""
                QTreeWidget {
                    background-color: white;
                    color: black;
                    border: none;
                    alternate-background-color: #f9f9f9;
                }
                QTreeWidget::item {
                    padding: 5px;
                }
                QTreeWidget::item:alternate {
                    background-color: #f9f9f9;
                }
                QTreeWidget::item:selected {
                    background-color: #e0e0e0;
                    color: black;
                }
                QHeaderView::section {
                    background-color: #f0f0f0;
                    color: black;
                }
            """)

    def update_ui(self, data):
        # logging.debug("update_ui called")
        try:
            self.tree.setUpdatesEnabled(False)
            
            for hw in data:
                hw_name = hw['Name']
                hw_id = f"HW|{hw_name}"
                
                # Check if Hardware item exists anywhere
                if hw_id in self.items_map:
                    hw_item = self.items_map[hw_id]
                else:
                    hw_item = QTreeWidgetItem(self.tree)
                    hw_item.setText(0, hw_name)
                    hw_item.setExpanded(True)
                    hw_item.setFlags(hw_item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
                    self.items_map[hw_id] = hw_item
                
                # Process Sensors
                self._update_sensors(hw_item, hw['Sensors'], hw_name)
                
            self.alert_manager.check_alerts(data)
            self.tree.setUpdatesEnabled(True)
        except Exception as e:
            import logging
            logging.error(f"Error in update_ui: {e}", exc_info=True)

    def open_menu(self, position):
        item = self.tree.itemAt(position)
        if not item: 
            return
            
        menu = QMenu()
        
        # Only allow alerts on leaf nodes (sensors)
        # A simple heuristic: if it has a value in column 1, it's likely a sensor
        if item.text(1):
            set_alert_action = QAction("Set Alert", self)
            set_alert_action.triggered.connect(lambda: self.set_alert_dialog(item))
            menu.addAction(set_alert_action)
            
            # Check if alert exists
            sensor_name = item.text(0)
            if sensor_name in self.alert_manager.alerts:
                remove_alert_action = QAction("Remove Alert", self)
                remove_alert_action.triggered.connect(lambda: self.alert_manager.remove_alert(sensor_name))
                menu.addAction(remove_alert_action)
            
        menu.exec(QCursor.pos())

    def set_alert_dialog(self, item):
        sensor_name = item.text(0)
        current_val = item.text(1)
        
        # Simple dialog for now, could be a custom dialog for more options
        max_val, ok = QInputDialog.getDouble(self, "Set Max Alert", 
                                            f"Trigger alert if {sensor_name} goes above:", 
                                            decimals=2)
        if ok:
            self.alert_manager.set_alert(sensor_name, max_val=max_val)
            QMessageBox.information(self, "Alert Set", f"Alert set for {sensor_name} > {max_val}")

    def _update_sensors(self, parent_item, sensors, hw_name):
        # Group sensors by type (Voltages, Temperatures, etc.)
        sensors_by_type = {}
        for sensor in sensors:
            s_type = sensor['Type']
            if s_type not in sensors_by_type:
                sensors_by_type[s_type] = []
            sensors_by_type[s_type].append(sensor)
            
        for s_type, s_list in sensors_by_type.items():
            type_id = f"TYPE|{hw_name}|{s_type}"
            
            # Check if Type item exists anywhere
            if type_id in self.items_map:
                type_item = self.items_map[type_id]
            else:
                type_item = QTreeWidgetItem(parent_item)
                type_item.setText(0, s_type)
                type_item.setExpanded(True)
                type_item.setFlags(type_item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
                self.items_map[type_id] = type_item
            
            for sensor in s_list:
                s_name = sensor['Name']
                sensor_id = f"SENSOR|{hw_name}|{s_type}|{s_name}"
                
                def safe_fmt(val):
                    if val is None:
                        return "N/A"
                    try:
                        return f"{val:.2f}"
                    except:
                        return str(val)

                val_str = safe_fmt(sensor.get('Value'))
                min_str = safe_fmt(sensor.get('Min'))
                max_str = safe_fmt(sensor.get('Max'))
                
                # Add units
                if s_type == 'Temperature':
                    unit = " °C"
                elif s_type == 'Voltage':
                    unit = " V"
                elif s_type == 'Load':
                    unit = " %"
                elif s_type == 'Fan':
                    unit = " RPM"
                elif s_type == 'Clock':
                    unit = " MHz"
                elif s_type == 'Power':
                    unit = " W"
                else:
                    unit = ""
                
                if sensor_id in self.items_map:
                    item = self.items_map[sensor_id]
                    item.setText(1, val_str + unit)
                    item.setText(2, min_str + unit)
                    item.setText(3, max_str + unit)
                else:
                    item = QTreeWidgetItem(type_item)
                    item.setText(0, s_name)
                    item.setText(1, val_str + unit)
                    item.setText(2, min_str + unit)
                    item.setText(3, max_str + unit)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
                    self.items_map[sensor_id] = item

    def show_error(self, message):
        QMessageBox.critical(self, "Error", message)

    def closeEvent(self, event):
        self.worker.stop()
        self.worker.wait()
        self.monitor.close()
        event.accept()

if __name__ == "__main__":
    # Global exception hook to catch early crashes
    def exception_hook(exctype, value, traceback):
        import traceback as tb
        error_msg = "".join(tb.format_exception(exctype, value, traceback))
        # Write to a file in the same directory as the exe
        log_path = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__), 'crash_log.txt')
        with open(log_path, 'w') as f:
            f.write(error_msg)
        # Also try standard logging
        logging.critical("Uncaught exception:", exc_info=(exctype, value, traceback))
        sys.__excepthook__(exctype, value, traceback)

    sys.excepthook = exception_hook

    try:
        app = QApplication(sys.argv)
        window = HWMonitorWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        import logging
        logging.critical(f"Critical UI error: {e}", exc_info=True)
