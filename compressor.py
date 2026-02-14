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
                    # WebP 支持 RGBA，保留透明度
                    if img.mode not in ('RGB', 'RGBA'):
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        else:
                            img = img.convert('RGBA')
                elif out_ext == '.png':
                    save_format = 'PNG'
                    # 强制将 P 模式转为 RGBA，防止 Resize 或保存过程中透明度丢失变黑
                    if img.mode == 'P' or img.mode not in ('RGB', 'RGBA'):
                        img = img.convert('RGBA')
                elif out_ext == '.webp': 
                    save_format = 'WEBP'
                    if img.mode not in ('RGB', 'RGBA'):
                        img = img.convert('RGBA')
                else:
                    # Default/Fallback: JPEG (or BMP/TIFF which we treat as RGB)
                    # 这些格式不支持透明度，必须处理背景色
                    save_format = 'JPEG'
                    
                    # 检查是否有透明通道
                    has_alpha = False
                    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                        has_alpha = True
                    
                    if has_alpha:
                        # 创建白色背景并将原图合成上去，防止透明变黑
                        if img.mode != 'RGBA':
                            img = img.convert('RGBA')
                        
                        background = Image.new('RGBA', img.size, (255, 255, 255, 255))
                        # 使用 alpha_composite 合成 (前提是两个图都是 RGBA)
                        img = Image.alpha_composite(background, img).convert('RGB')
                    elif img.mode != 'RGB':
                        # 如果没有透明通道但不是 RGB (例如 CMYK, L)，直接转 RGB
                        img = img.convert('RGB')
                
                # 1. 调整尺寸 (Resizing)
                if max_width and img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                
                # --- 核心逻辑: 针对不同格式的压缩策略 ---
                
                # 辅助函数: 获取当前图像数据大小
                def get_size(img_obj, fmt, **kwargs):
                    buf = BytesIO()
                    img_obj.save(buf, format=fmt, **kwargs)
                    return buf.tell(), buf.getvalue()

                # --- 分支 1: 固定质量模式 ---
                if fixed_quality:
                    if save_format == 'PNG':
                        # PNG 即使是固定质量，如果质量设置较低，也应该尝试减色以减小体积
                        # 假设 quality < 90 时开始尝试减色 (90-100 视为无损/高质量)
                        if quality < 90:
                            # 映射 quality (0-90) 到 colors (2-256)
                            colors = max(2, int((quality / 90) * 256))
                            try:
                                # method=2 (MEDIANCUT) 通常能较好保留透明度
                                img = img.quantize(colors=colors, method=2)
                            except:
                                pass # 如果出错保持原样
                        
                        img.save(output_path, format='PNG', optimize=True)
                        result_msg = f"Fixed Quality (PNG Optimized, Q={quality})"
                    else:
                        # JPEG / WebP
                        img.save(output_path, format=save_format, quality=quality)
                        result_msg = f"Fixed Quality (Q={quality})"
                                            
                    size_kb = os.path.getsize(output_path) / 1024
                    return True, result_msg, size_kb

                # --- 分支 2: 目标大小模式 (智能压缩) ---
                target_size_bytes = target_size_kb * 1024
                
                # A. 针对 PNG 的特殊二分/循环逻辑 (因为 quality 参数无效)
                if save_format == 'PNG':
                    # 1. 先尝试直接保存 (RGBA, optimize=True)
                    size, data = get_size(img, 'PNG', optimize=True)
                    if size <= target_size_bytes:
                        with open(output_path, 'wb') as f: f.write(data)
                        return True, "PNG Optimized (Lossless)", size / 1024
                    
                    # 2. 如果不行，开始减色 (Quantize) 循环
                    # 颜色从 256 递减到 8
                    # 为了效率，我们取几个关键点或者二分，这里用步进尝试
                    color_steps = [256, 192, 128, 96, 64, 32, 16, 8]
                    best_data = data # 默认存之前的
                    best_size = size
                    
                    for c in color_steps:
                        try:
                            # 注意: quantize 会返回新图片
                            q_img = img.quantize(colors=c, method=2)
                            curr_size, curr_data = get_size(q_img, 'PNG', optimize=True)
                            
                            if curr_size <= target_size_bytes:
                                with open(output_path, 'wb') as f: f.write(curr_data)
                                return True, f"PNG Quantized (Colors={c})", curr_size / 1024
                            
                            # 记录最小的那个，以防都达不到目标
                            if curr_size < best_size:
                                best_size = curr_size
                                best_data = curr_data
                        except:
                            continue

                    # 如果所有尝试都失败，保存最小的那个
                    with open(output_path, 'wb') as f: f.write(best_data)
                    return True, f"Warning: Hard limit reached (PNG Min Size)", best_size / 1024

                # B. 针对 JPEG / WEBP 的常规 Quality 二分逻辑
                else: 
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
                    
                    # 1. 调整大小
                    if max_width and f.width > max_width:
                        ratio = max_width / f.width
                        new_height = int(f.height * ratio)
                        # 使用 LANCZOS 可能会产生半透明像素，这对 GIF 是不利的
                        f = f.resize((max_width, new_height), Image.Resampling.LANCZOS)
                    
                    # 2. 处理 GIF 格式的透明度问题 (关键步骤)
                    # GIF只支持全透或全不透。Resize 产生的半透明像素(Alpha 1-254)会被强制转换，通常变成黑色杂边。
                    if not to_webp: # 如果是转 WebP，保留半透明甚至更好
                        if f.mode == 'P':
                            f = f.convert('RGBA')
                        
                        if f.mode == 'RGBA':
                             # 二值化 Alpha 通道：透明度 < 128 设为 0 (全透)，>= 128 设为 255 (不透)
                             # 这能消除因 Resize 产生的半透明黑边
                             alpha = f.getchannel('A')
                             # 这种方式比 point 效率稍低但更直观，point 写法: alpha.point(lambda p: 255 if p > 128 else 0)
                             threshold = 128
                             f.putalpha(alpha.point(lambda p: 255 if p > threshold else 0))
                    
                    if to_webp:
                        if f.mode not in ('RGB', 'RGBA'):
                             f = f.convert('RGBA')
                    
                    frames.append(f)

                if not frames:
                    return False, "No frames found", 0

                # 保存
                if to_webp or output_path.lower().endswith('.webp'):
                    # 保存为 WebP (支持动画, 支持半透明)
                    frames[0].save(
                        output_path, 
                        save_all=True, 
                        append_images=frames[1:], 
                        optimize=True,
                        quality=80, # WebP 动画质量
                        method=6
                    )
                else:
                    # 保存为 GIF
                    # disposal=2: 恢复背景色 (防止帧叠加残影)
                    # transparency=0/255: 通常不需要显式指定，PIL 会自动处理 RGBA->P 的量化
                    # 但最好将第一帧的 info 复制过去，这有点复杂，通常直接 save 即可
                    frames[0].save(
                        output_path, 
                        save_all=True, 
                        append_images=frames[1:], 
                        optimize=True,
                        disposal=2, # 关键：每帧播放完后恢复背景，防止透明叠加导致后面变乱
                        loop=img.info.get('loop', 0) # 保留循环次数
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
