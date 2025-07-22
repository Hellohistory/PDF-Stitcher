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

        # 使用页码作为文件名，确保顺序
        image_path = os.path.join(temp_dir, f"page_{page_num:05d}.png")
        img.save(image_path, format='PNG')
        return image_path
    except Exception as e:
        print(f"Error processing page {page_num}: {e}")
        return None


def extract_images_from_pdf(pdf_path, zoom_factor, temp_dir, log_callback):
    """从PDF文件中提取所有页面为图像。"""
    try:
        log_callback(f"🚀 开始处理文件: {os.path.basename(pdf_path)}")
        pdf_doc = fitz.open(pdf_path)
        zoom_matrix = fitz.Matrix(zoom_factor, zoom_factor)
        image_paths = []

        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            future_to_page = {
                executor.submit(process_page, pdf_doc, page_num, zoom_matrix, temp_dir): page_num
                for page_num in range(len(pdf_doc))
            }
            results = []
            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                result_path = future.result()
                if result_path:
                    # 存储页码和路径，以便稍后排序
                    results.append((page_num, result_path))

        # 确保图像按正确的页面顺序排列
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


def concatenate_images_vertically(image_paths, output_image_base_path, images_per_long, log_callback):
    """将一组图像垂直拼接成一张或多张长图。"""
    if not image_paths:
        return

    total_images = len(image_paths)
    num_long_images = (total_images + images_per_long - 1) // images_per_long

    for i in range(0, total_images, images_per_long):
        chunk_paths = image_paths[i:i + images_per_long]
        part_num = (i // images_per_long) + 1

        try:
            images_to_stitch = [Image.open(p) for p in chunk_paths]

            # 检查尺寸，Pillow有65535像素的限制
            total_height = sum(img.height for img in images_to_stitch)
            max_width = max(img.width for img in images_to_stitch)

            if total_height > MAX_IMAGE_DIMENSION:
                log_callback(
                    f"警告: 第 {part_num} 部分高度过高 ({total_height}px)，将跳过拼接。请尝试减少'每张长图的图片数量'。")
                continue

            # 创建新的空白长图
            long_image = Image.new("RGB", (max_width, total_height))
            y_offset = 0
            for img in images_to_stitch:
                long_image.paste(img, (0, y_offset))
                y_offset += img.height
                img.close()  # 及时关闭图片文件句柄

            # 根据是否有多张长图决定文件名
            if num_long_images > 1:
                output_path = f"{output_image_base_path}_part{part_num}.jpg"
            else:
                output_path = f"{output_image_base_path}.jpg"

            long_image.save(output_path, "JPEG", quality=95)  # 使用JPEG并指定质量
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