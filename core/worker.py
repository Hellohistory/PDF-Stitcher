# core/worker.py
import os
import tempfile
from PySide2.QtCore import QThread, Signal
from . import converter


class BatchConvertWorker(QThread):
    # 新的信号，可以传递一个整数(百分比)和一个字符串(状态文本)
    update_detailed_progress = Signal(int, str)
    log_message = Signal(str)
    finished = Signal(dict)

    def __init__(self, pdf_files, output_folder, zoom, images_per_long):
        super().__init__()
        self.pdf_files = pdf_files
        self.output_folder = output_folder
        self.zoom_factor = zoom
        self.images_per_long = images_per_long
        self.temp_dir = tempfile.mkdtemp(prefix="pdf2img_")
        self.current_pdf_filename = ""

    def _handle_page_progress(self, completed, total):
        """根据页面进度计算总体进度并发送信号"""
        if total == 0:
            return

        page_progress_percent = (completed / total)
        current_file_progress = page_progress_percent * self.file_progress_span
        overall_progress = int(self.base_progress + current_file_progress)

        status_text = f"正在处理: {self.current_pdf_filename} ({completed}/{total} 页)"
        self.update_detailed_progress.emit(overall_progress, status_text)

    def run(self):
        total_files = len(self.pdf_files)
        failed_files = []

        self.base_progress = 0
        self.file_progress_span = 100 / total_files if total_files > 0 else 0

        for i, pdf_file in enumerate(self.pdf_files):
            try:
                self.current_pdf_filename = os.path.basename(pdf_file)
                self.base_progress = int(i / total_files * 100)

                base_name = os.path.splitext(self.current_pdf_filename)[0]
                output_base_path = os.path.join(self.output_folder, base_name)

                image_paths = converter.extract_images_from_pdf(
                    pdf_file,
                    self.zoom_factor,
                    self.temp_dir,
                    self.log_message.emit,
                    progress_callback=self._handle_page_progress
                )

                if image_paths:
                    self.update_detailed_progress.emit(
                        int(self.base_progress + self.file_progress_span * 0.9),  # 假设拼接占10%时间
                        f"正在拼接: {self.current_pdf_filename}..."
                    )
                    converter.concatenate_images_vertically(
                        image_paths, output_base_path, self.images_per_long, self.log_message.emit
                    )
                else:
                    self.update_detailed_progress.emit(
                        int(self.base_progress + self.file_progress_span),
                        f"文件跳过 (无内容): {self.current_pdf_filename}"
                    )
                    # 虽然没提取出图片，但不一定是失败，可能是空PDF

            except Exception as e:
                failed_files.append(self.current_pdf_filename)
                self.log_message.emit(f"❌ 文件 {self.current_pdf_filename} 转换失败: {e}")

            finally:
                # 确保每个文件循环结束时，进度条都准确地到达下一个文件的起点
                progress = int((i + 1) / total_files * 100)
                self.update_detailed_progress.emit(
                    progress,
                    f"文件处理完成: {self.current_pdf_filename}"
                )

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