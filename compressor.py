import os
from PIL import Image, ImageFile, ImageSequence
import fitz # PyMuPDF

from io import BytesIO

# 防止 Pillow 报错 "Image file truncated"
ImageFile.LOAD_TRUNCATED_IMAGES = True

class ImageCompressor:
    def __init__(self):
        self.supported_formats = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.pdf')

    def compress_image(self, file_path, output_path, target_size_kb=None, 
                       max_width=None, to_webp=False, quality=95, fixed_quality=False):
        """
        压缩单个图片
        :param file_path: 原文件路径
        :param output_path: 输出文件路径
        :param target_size_kb: 目标大小 (KB)。如果 fixed_quality=True，此参数被忽略。
        :param max_width: 最大宽度 (px)，None 表示不调整
        :param to_webp: 是否转换为 WebP 格式
        :param quality: 初始质量 (如果 fixed_quality=True，则直接使用此质量)
        :param fixed_quality: 是否使用固定质量模式
        :return: (success, message, final_size_kb)
        """
        # 预检查文件类型
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            return self.compress_pdf(file_path, output_path)
            
        if ext == '.gif':
            return self.compress_gif(file_path, output_path, max_width, to_webp)

        try:
            # 打开图片
            with Image.open(file_path) as img:
                # 转换颜色模式 & 确定保存格式
                out_ext = os.path.splitext(output_path)[1].lower()
                
                if to_webp:
                    save_format = 'WEBP'
                    if img.mode not in ('RGB', 'RGBA'):
                        img = img.convert('RGBA')
                elif out_ext == '.png':
                    save_format = 'PNG'
                    # PNG supports RGBA, keep it if present
                    if img.mode not in ('RGB', 'RGBA', 'P'):
                        img = img.convert('RGBA')
                elif out_ext == '.webp': 
                    save_format = 'WEBP'
                    if img.mode not in ('RGB', 'RGBA'):
                        img = img.convert('RGBA')
                else:
                    # Default to JPEG
                    save_format = 'JPEG'
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                
                # 1. 调整尺寸 (Resizing)
                if max_width and img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                
                # --- 分支 1: 固定质量模式 ---
                if fixed_quality:
                    if save_format == 'PNG':
                        # PNG quality is not supported in the same way, use optimize=True
                         img.save(output_path, format=save_format, optimize=True)
                    else:
                        img.save(output_path, format=save_format, quality=quality)
                                            
                    size_kb = os.path.getsize(output_path) / 1024
                    return True, f"Fixed Quality (Q={quality})", size_kb

                # --- 分支 2: 目标大小模式 (智能压缩) ---
                target_size_bytes = target_size_kb * 1024
                buffer = BytesIO()
                
                min_q = 5
                max_q = quality # 使用传入的 quality 作为起始最高质量
                
                # 第一次尝试
                buffer.seek(0); buffer.truncate(0)
                img.save(buffer, format=save_format, quality=max_q)
                size = buffer.tell()
                
                if size <= target_size_bytes:
                    with open(output_path, 'wb') as f:
                        f.write(buffer.getvalue())
                    return True, "Success", size / 1024
                
                # 二分法逼近
                final_q = max_q
                left = min_q
                right = max_q
                best_buffer = None
                
                while left <= right:
                    mid = (left + right) // 2
                    buffer.seek(0); buffer.truncate(0)
                    img.save(buffer, format=save_format, quality=mid)
                    size = buffer.tell()
                    
                    if size <= target_size_bytes:
                        best_buffer = buffer.getvalue()
                        final_q = mid
                        left = mid + 1
                    else:
                        right = mid - 1
                
                if best_buffer:
                    with open(output_path, 'wb') as f:
                        f.write(best_buffer)
                    return True, f"Smart Compressed (Q={final_q})", len(best_buffer) / 1024
                else:
                    # 硬限制无法满足
                    buffer.seek(0); buffer.truncate(0)
                    img.save(buffer, format=save_format, quality=min_q)
                    with open(output_path, 'wb') as f:
                        f.write(buffer.getvalue())
                    return True, f"Warning: Hard limit reached (Q={min_q})", buffer.tell() / 1024

        except Exception as e:
            return False, str(e), 0

    def compress_gif(self, file_path, output_path, max_width=None, to_webp=False):
        try:
            with Image.open(file_path) as img:
                frames = []
                # 遍历所有帧
                for frame in ImageSequence.Iterator(img):
                    f = frame.copy()
                    
                    # 调整大小
                    if max_width and f.width > max_width:
                        ratio = max_width / f.width
                        new_height = int(f.height * ratio)
                        f = f.resize((max_width, new_height), Image.Resampling.LANCZOS)
                    
                    if to_webp:
                        if f.mode not in ('RGB', 'RGBA'):
                            f = f.convert('RGBA')
                    
                    frames.append(f)

                if not frames:
                    return False, "No frames found", 0

                # 保存
                if to_webp or output_path.lower().endswith('.webp'):
                    # 保存为 WebP (支持动画)
                    frames[0].save(
                        output_path, 
                        save_all=True, 
                        append_images=frames[1:], 
                        optimize=True,
                        quality=80,
                        method=6
                    )
                else:
                    # 保存为 GIF
                    frames[0].save(
                        output_path, 
                        save_all=True, 
                        append_images=frames[1:], 
                        optimize=True
                    )
                
                size_kb = os.path.getsize(output_path) / 1024
                return True, "GIF Optimized", size_kb

        except Exception as e:
            return False, f"GIF Error: {e}", 0

    def compress_pdf(self, file_path, output_path):
        try:
            doc = fitz.open(file_path)
            # 使用 garbage=4 (去重+清理) 和 deflate=True (压缩流)
            doc.save(output_path, garbage=4, deflate=True)
            doc.close()
            
            size_kb = os.path.getsize(output_path) / 1024
            return True, "PDF Compressed", size_kb
        except Exception as e:
            return False, f"PDF Error: {e}", 0

    def process_queue(self, file_list, output_dir, params, progress_callback=None):
        """
        批量处理队列
        """
        results = []
        total = len(file_list)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        for i, file_path in enumerate(file_list):
            filename = os.path.basename(file_path)
            # 确定输出文件名
            name, ext = os.path.splitext(filename)
            if params.get('to_webp'):
                out_filename = f"{name}.webp"
            elif ext.lower() == '.png':
                out_filename = f"{name}.png"
            elif ext.lower() == '.webp':
                out_filename = f"{name}.webp"
            else:
                out_filename = f"{name}.jpg"

            output_path = os.path.join(output_dir, out_filename)
            
            success, msg, size = self.compress_image(
                file_path, 
                output_path, 
                target_size_kb=params.get('target_size_kb'),
                max_width=params.get('max_width'),
                to_webp=params.get('to_webp'),
                quality=params.get('quality', 95),
                fixed_quality=params.get('fixed_quality', False)
            )
            
            results.append((filename, success, msg, size))
            
            if progress_callback:
                progress_callback(i + 1, total, filename)
                
        return results
