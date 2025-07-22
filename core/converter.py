# core/converter.py
import os
from PIL import Image
import fitz  # PyMuPDF
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_IMAGE_DIMENSION = 65500  # Pillow的最大支持尺寸


def process_page(pdf_doc, page_num, zoom_matrix, temp_dir):
    """处理单个PDF页面，将其转换为图像。"""
    try:
        page = pdf_doc.load_page(page_num)
        pix = page.get_pixmap(matrix=zoom_matrix)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        image_path = os.path.join(temp_dir, f"page_{page_num:05d}.png")
        img.save(image_path, format='PNG')
        return image_path
    except Exception as e:
        print(f"Error processing page {page_num}: {e}")
        return None


def extract_images_from_pdf(pdf_path, zoom_factor, temp_dir, log_callback, progress_callback=None):
    """从PDF文件中提取所有页面为图像。"""
    try:
        log_callback(f"🚀 开始处理文件: {os.path.basename(pdf_path)}")
        pdf_doc = fitz.open(pdf_path)
        total_pages = len(pdf_doc)
        zoom_matrix = fitz.Matrix(zoom_factor, zoom_factor)
        image_paths = []

        if total_pages == 0:
            log_callback(f"⚠️ 文件为空，无页面可处理: {os.path.basename(pdf_path)}")
            if progress_callback:
                progress_callback(0, 0)
            return []

        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            future_to_page = {
                executor.submit(process_page, pdf_doc, page_num, zoom_matrix, temp_dir): page_num
                for page_num in range(total_pages)
            }
            results = []

            completed_pages = 0
            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                result_path = future.result()

                completed_pages += 1
                if progress_callback:
                    progress_callback(completed_pages, total_pages)

                if result_path:
                    results.append((page_num, result_path))

        results.sort(key=lambda x: x[0])
        image_paths = [path for _, path in results]

        if not image_paths:
            log_callback(f"⚠️ 文件未能提取任何图片: {os.path.basename(pdf_path)}")
        else:
            log_callback(f"✅ 页面提取完成: {os.path.basename(pdf_path)}")

        return image_paths
    except Exception as e:
        log_callback(f"❌ 处理PDF失败: {pdf_path}, 错误: {e}")
        return []


# --- 函数已重构以优化内存并支持格式控制 ---
def concatenate_images_vertically(image_paths, output_image_base_path, images_per_long, log_callback, output_format,
                                  quality):
    """将一组图像垂直拼接成一张或多张长图（内存优化版）。"""
    if not image_paths:
        return

    total_images = len(image_paths)
    file_extension = output_format.lower()

    for i in range(0, total_images, images_per_long):
        chunk_paths = image_paths[i:i + images_per_long]
        part_num = (i // images_per_long) + 1

        try:
            # --- 步骤1: 预扫描以获取尺寸 ---
            log_callback(f"  - 正在分析第 {part_num} 部分的尺寸...")
            total_height = 0
            max_width = 0
            for p in chunk_paths:
                with Image.open(p) as img:
                    total_height += img.height
                    if img.width > max_width:
                        max_width = img.width

            if total_height > MAX_IMAGE_DIMENSION:
                log_callback(
                    f"⚠️ 警告: 第 {part_num} 部分高度过高 ({total_height}px)，将跳过拼接。请尝试减少'每张长图的图片数量'。")
                continue

            # --- 步骤2: 创建画布并逐个粘贴 ---
            log_callback(f"  - 正在创建第 {part_num} 部分的画布 (尺寸: {max_width}x{total_height})...")
            long_image = Image.new("RGB", (max_width, total_height))
            y_offset = 0
            for p in chunk_paths:
                with Image.open(p) as img:
                    long_image.paste(img, (0, y_offset))
                    y_offset += img.height

            # 根据是否有多张长图决定文件名
            num_long_images = (total_images + images_per_long - 1) // images_per_long
            if num_long_images > 1:
                output_path = f"{output_image_base_path}_part{part_num}.{file_extension}"
            else:
                output_path = f"{output_image_base_path}.{file_extension}"

            # --- 根据格式进行保存 ---
            if output_format == 'JPEG':
                long_image.save(output_path, "JPEG", quality=quality)
            elif output_format == 'PNG':
                long_image.save(output_path, "PNG")

            log_callback(f"🎉 已生成长图: {os.path.basename(output_path)}")

        except Exception as e:
            log_callback(f"❌ 拼接图片失败 (Part {part_num}): {e}")
        finally:
            # 清理这一批的临时文件
            for path in chunk_paths:
                try:
                    os.remove(path)
                except OSError:
                    pass