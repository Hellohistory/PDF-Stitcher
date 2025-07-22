# core/worker.py
import os
import tempfile
from PySide2.QtCore import QThread, Signal
from . import converter


class BatchConvertWorker(QThread):
    # 定义信号
    update_progress = Signal(int)
    log_message = Signal(str)
    finished = Signal(dict)

    def __init__(self, pdf_files, output_folder, zoom, images_per_long):
        super().__init__()
        self.pdf_files = pdf_files
        self.output_folder = output_folder
        self.zoom_factor = zoom
        self.images_per_long = images_per_long
        self.temp_dir = tempfile.mkdtemp(prefix="pdf2img_")

    def run(self):
        total_files = len(self.pdf_files)
        failed_files = []

        for i, pdf_file in enumerate(self.pdf_files):
            try:
                # 定义长图的基础文件名
                base_name = os.path.splitext(os.path.basename(pdf_file))[0]
                output_base_path = os.path.join(self.output_folder, base_name)

                # 1. 从PDF提取所有页面为单个图像
                image_paths = converter.extract_images_from_pdf(
                    pdf_file, self.zoom_factor, self.temp_dir, self.log_message.emit
                )

                # 2. 将提取的图像拼接成长图
                if image_paths:
                    converter.concatenate_images_vertically(
                        image_paths, output_base_path, self.images_per_long, self.log_message.emit
                    )
                else:
                    raise ValueError("未能从PDF中提取任何图像。")

            except Exception as e:
                failed_files.append(os.path.basename(pdf_file))
                self.log_message.emit(f"❌ 文件 {os.path.basename(pdf_file)} 转换失败: {e}")

            # 更新总体进度
            progress = int((i + 1) / total_files * 100)
            self.update_progress.emit(progress)

        # 清理临时文件夹
        try:
            for f in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, f))
            os.rmdir(self.temp_dir)
            self.log_message.emit("🧹 临时文件已清理。")
        except Exception as e:
            self.log_message.emit(f"⚠️ 清理临时文件失败: {e}")

        summary = {"failed": failed_files}
        self.finished.emit(summary)