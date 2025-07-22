# ui/main_window.py
import json
import os

from PySide2.QtCore import Qt
from PySide2.QtGui import QIcon, QDragEnterEvent, QDropEvent
from PySide2.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                               QFileDialog, QProgressBar, QSpinBox, QHBoxLayout, QLineEdit,
                               QMessageBox, QTextEdit, QComboBox)

from core.worker import BatchConvertWorker


class MainWindow(QWidget):
    VERSION = "v1.0.1"

    def __init__(self):
        super().__init__()
        self.pdf_files = []
        self.worker = None
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setWindowTitle(f'PDF转长图工具 {self.VERSION} (By Hellohistory)')
        self.setWindowIcon(QIcon('assets/logo.ico'))
        self.setGeometry(200, 200, 600, 580)  # 稍微增加高度以容纳新控件
        self.setAcceptDrops(True)

        layout = QVBoxLayout()

        self.pdf_path_line_edit = QLineEdit(placeholderText="请点击按钮选择PDF文件，或将文件/文件夹拖拽至此")
        self.pdf_path_line_edit.setReadOnly(True)
        self.btn_select_pdf = QPushButton('选择PDF文件')
        self.btn_select_pdf.clicked.connect(self.select_pdf_files)
        pdf_layout = QHBoxLayout()
        pdf_layout.addWidget(self.pdf_path_line_edit)
        pdf_layout.addWidget(self.btn_select_pdf)
        layout.addLayout(pdf_layout)

        params_layout = QHBoxLayout()
        params_layout.addWidget(QLabel("图像清晰度 (1-5):"))
        self.zoom_spinbox = QSpinBox(minimum=1, maximum=5, value=2)
        params_layout.addWidget(self.zoom_spinbox)
        params_layout.addStretch()
        params_layout.addWidget(QLabel("每张长图页数:"))
        self.pages_per_image_spinbox = QSpinBox(minimum=1, maximum=200, value=10)
        params_layout.addWidget(self.pages_per_image_spinbox)
        layout.addLayout(params_layout)

        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("输出格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPEG", "PNG"])
        format_layout.addWidget(self.format_combo)

        self.quality_label = QLabel("JPEG质量:")
        self.quality_spinbox = QSpinBox(minimum=10, maximum=100, value=95)
        format_layout.addWidget(self.quality_label)
        format_layout.addWidget(self.quality_spinbox)
        format_layout.addStretch()

        # 信号连接，当格式改变时，控制质量选项的显隐
        self.format_combo.currentIndexChanged.connect(self.on_format_changed)
        layout.addLayout(format_layout)

        self.save_path_line_edit = QLineEdit(placeholderText="请选择转换后图片的保存文件夹")
        self.btn_select_save = QPushButton('选择保存位置')
        self.btn_select_save.clicked.connect(self.select_save_folder)
        save_layout = QHBoxLayout()
        save_layout.addWidget(self.save_path_line_edit)
        save_layout.addWidget(self.btn_select_save)
        layout.addLayout(save_layout)
        self.log_box = QTextEdit(readOnly=True)
        layout.addWidget(self.log_box)

        # ... (进度条和按钮部分保持不变，只是位置调整) ...
        self.progress_bar = QProgressBar(textVisible=True, alignment=Qt.AlignCenter)
        self.status_label = QLabel("一切就绪，请选择文件开始转换。")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.btn_start = QPushButton('开始转换')
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self.start_conversion)
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.progress_bar)
        bottom_layout.addWidget(self.btn_start)
        layout.addLayout(bottom_layout)
        layout.addWidget(self.status_label)

        self.setLayout(layout)
        self.apply_stylesheet()

    def on_format_changed(self, index):
        is_jpeg = (self.format_combo.currentText() == "JPEG")
        self.quality_label.setVisible(is_jpeg)
        self.quality_spinbox.setVisible(is_jpeg)

    def start_conversion(self):
        self.btn_start.setEnabled(False)
        self.log_box.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("任务准备中...")

        self.worker = BatchConvertWorker(
            pdf_files=self.pdf_files,
            output_folder=self.save_path_line_edit.text(),
            zoom=self.zoom_spinbox.value(),
            images_per_long=self.pages_per_image_spinbox.value(),
            output_format=self.format_combo.currentText(),
            quality=self.quality_spinbox.value()
        )

        self.worker.log_message.connect(self.log_box.append)
        self.worker.update_detailed_progress.connect(self.on_detailed_progress_update)
        self.worker.finished.connect(self.on_conversion_finished)
        self.worker.start()

    def load_settings(self):
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", "r") as f:
                    settings = json.load(f)
                    self.save_path_line_edit.setText(settings.get("save_path", ""))
                    self.zoom_spinbox.setValue(settings.get("zoom_factor", 2))
                    self.pages_per_image_spinbox.setValue(settings.get("pages_per_image", 10))
                    # --- 新增: 加载格式与质量设置 ---
                    self.format_combo.setCurrentText(settings.get("output_format", "JPEG"))
                    self.quality_spinbox.setValue(settings.get("quality", 95))
        except (IOError, json.JSONDecodeError):
            pass
        finally:
            self.on_format_changed(self.format_combo.currentIndex())

    def save_settings(self):
        settings = {
            "save_path": self.save_path_line_edit.text(),
            "zoom_factor": self.zoom_spinbox.value(),
            "pages_per_image": self.pages_per_image_spinbox.value(),
            # --- 新增: 保存格式与质量设置 ---
            "output_format": self.format_combo.currentText(),
            "quality": self.quality_spinbox.value(),
        }
        with open("settings.json", "w") as f:
            json.dump(settings, f, indent=4)

    # --- 其他函数保持不变 ---
    def apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget { font-family: 'Microsoft YaHei'; background-color: #f0f0f0; }
            QLabel { font-size: 14px; color: #333; }
            QLineEdit, QSpinBox, QTextEdit, QComboBox { 
                border: 1px solid #ccc; border-radius: 4px; padding: 5px; 
                background-color: #fff; color: #333;
            }
            QPushButton { 
                background-color: #0078d7; color: white; border: none;
                border-radius: 4px; padding: 8px 12px; font-size: 14px;
            }
            QPushButton:hover { background-color: #005a9e; }
            QPushButton:disabled { background-color: #a0a0a0; }
            QProgressBar { text-align: center; border-radius: 5px; height: 24px; }
            QProgressBar::chunk { background-color: #0078d7; border-radius: 5px; }
            #status_label { color: #555; font-size: 12px; }
        """)
        self.status_label.setObjectName("status_label")

    def select_pdf_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择一个或多个PDF文件", "", "PDF Files (*.pdf)")
        if files:
            self.pdf_files = files
            self.pdf_path_line_edit.setText(f"已选择 {len(files)} 个文件")
            self.check_readiness()

    def select_save_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择保存文件夹")
        if folder:
            self.save_path_line_edit.setText(folder)
            self.check_readiness()

    def check_readiness(self):
        ready = bool(self.pdf_files and self.save_path_line_edit.text())
        self.btn_start.setEnabled(ready)

    def on_detailed_progress_update(self, percent, text):
        self.progress_bar.setValue(percent)
        self.status_label.setText(text)

    def on_conversion_finished(self, summary):
        failed_count = len(summary['failed'])
        success_count = len(self.pdf_files) - failed_count

        if failed_count > 0:
            QMessageBox.warning(self, "转换有失败", f"{failed_count} 个文件转换失败:\n" + "\n".join(summary['failed']))
        else:
            QMessageBox.information(self, "转换完成", "所有PDF文件已成功转换为长图！")

        self.status_label.setText(f"任务完成！成功 {success_count} 个, 失败 {failed_count} 个。")
        self.progress_bar.setValue(100)

        self.pdf_files = []
        self.pdf_path_line_edit.clear()
        self.btn_start.setEnabled(False)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        dropped_files = []
        for url in urls:
            path = url.toLocalFile()
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for name in files:
                        if name.lower().endswith('.pdf'):
                            dropped_files.append(os.path.join(root, name))
            elif path.lower().endswith('.pdf'):
                # 如果是文件，直接添加
                dropped_files.append(path)

        if dropped_files:
            self.pdf_files = list(set(dropped_files))
            self.pdf_path_line_edit.setText(f"已拖拽并选择 {len(self.pdf_files)} 个文件")
            self.log_box.append(f"已添加 {len(self.pdf_files)} 个PDF文件。")
            self.check_readiness()

    def closeEvent(self, event):
        self.save_settings()
        event.accept()