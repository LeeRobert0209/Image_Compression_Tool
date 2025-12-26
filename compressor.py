import os
from PIL import Image, ImageFile
from io import BytesIO

# 防止 Pillow 报错 "Image file truncated"
ImageFile.LOAD_TRUNCATED_IMAGES = True

class ImageCompressor:
    def __init__(self):
        self.supported_formats = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')

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
        try:
            # 打开图片
            with Image.open(file_path) as img:
                # 转换颜色模式
                if to_webp:
                    save_format = 'WEBP'
                    if img.mode not in ('RGB', 'RGBA'):
                        img = img.convert('RGBA')
                else:
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
            else:
                out_filename = f"{name}.jpg" # 默认统一转jpg简单点，或者保持原后缀
                # 如果保持原后缀且不是webp
                if not params.get('to_webp'):
                   # 强制改为jpg如果原图不是jpg
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
