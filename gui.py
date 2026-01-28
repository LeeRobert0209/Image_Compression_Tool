import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from compressor import ImageCompressor

# --- 配置 ---
FONT_MAIN = ('SimSun', 10)
FONT_BOLD = ('SimSun', 10, 'bold')
FONT_LARGE = ('SimSun', 12, 'bold')
COLOR_BG = "#f0f0f0"
COLOR_ACCENT = "#4a90e2"

class CompressionToolApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("图片极限压缩工具 v1.0")
        self.geometry("400x500")
        self.configure(bg=COLOR_BG)

        self.compressor = ImageCompressor()
        self.files_to_process = []
        
        self._init_ui()
        

        
        # 延时强制显示窗口，确保主循环启动后再执行
        self.after(200, self.force_show_window)
        
    def force_show_window(self):
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            # 短暂置顶
            self.attributes("-topmost", True)
            self.after(100, lambda: self.attributes("-topmost", False))
        except Exception as e:
            print(f"Window activation error: {e}")
        
    def _init_ui(self):
        # 1. 顶部标题区
        header_frame = tk.Frame(self, bg=COLOR_BG, pady=10)
        header_frame.pack(fill='x')
        tk.Label(header_frame, text="图片批量压缩助手", font=('SimSun', 16, 'bold'), bg=COLOR_BG, fg="#333").pack()
        tk.Label(header_frame, text="支持拖拽文件或文件夹 | 智能压缩 | 格式转换", font=FONT_MAIN, bg=COLOR_BG, fg="#666").pack()

        # 2. 拖拽区域 (核心)
        self.drop_frame = tk.LabelFrame(self, text="  操作区域  ", font=FONT_BOLD, bg=COLOR_BG, fg="#333", width=360, height=150)
        self.drop_frame.pack(pady=10, padx=20, fill='x')
        self.drop_frame.pack_propagate(False) # 固定大小
        
        self.lbl_drop = tk.Label(self.drop_frame, 
                                 text="👇 请将图片或文件夹拖入此处 👇\n\n(支持 JPG, PNG, WebP, GIF, PDF)", 
                                 font=('SimSun', 11), bg="white", fg="#888",
                                 relief="groove", borderwidth=2, cursor="hand2")
        self.lbl_drop.pack(expand=True, fill='both', padx=10, pady=10)
        
        # 绑定拖拽事件
        self.lbl_drop.drop_target_register(DND_FILES)
        self.lbl_drop.dnd_bind('<<Drop>>', self.on_drop)
        self.lbl_drop.bind('<Button-1>', self.on_click_select)

        # 3. 参数设置区
        self.settings_frame = tk.LabelFrame(self, text="  压缩参数  ", font=FONT_BOLD, bg=COLOR_BG, fg="#333")
        self.settings_frame.pack(pady=5, padx=20, fill='x')
        
        # 3.1 模式选择 (Mode) 和 参数区的布局
        mode_frame = tk.Frame(self.settings_frame, bg=COLOR_BG)
        mode_frame.pack(fill='x', padx=10, pady=5)
        
        self.ctrl_frame = tk.Frame(self.settings_frame, bg=COLOR_BG)
        self.ctrl_frame.pack(fill='x', padx=10, pady=5)
        
        # 3.2 填充模式选择
        self.var_mode = tk.StringVar(value="auto") # auto (KB) or fixed (Quality)
        
        rb_auto = tk.Radiobutton(mode_frame, text="智能模式 (指定大小)", variable=self.var_mode, value="auto", command=self.update_mode_ui, bg=COLOR_BG, font=FONT_MAIN)
        rb_auto.pack(side='left')
        
        rb_fixed = tk.Radiobutton(mode_frame, text="固定质量 (指定比例)", variable=self.var_mode, value="fixed", command=self.update_mode_ui, bg=COLOR_BG, font=FONT_MAIN)
        rb_fixed.pack(side='left', padx=10)

        # 3.3 初始化滑块
        self.update_mode_ui()

        # 3.4 宽度限制 (Resize)
        row2 = tk.Frame(self.settings_frame, bg=COLOR_BG)
        row2.pack(fill='x', padx=10, pady=5)
        
        self.var_resize = tk.BooleanVar(value=False)
        self.chk_resize = ttk.Checkbutton(row2, text="限制最大宽度", variable=self.var_resize, command=self.toggle_resize)
        self.chk_resize.pack(side='left')
        
        self.combo_width = ttk.Combobox(row2, values=["1920", "1280", "1080", "800"], width=8, state='disabled')
        self.combo_width.set("1080")
        self.combo_width.pack(side='left', padx=5)
        tk.Label(row2, text="px", font=FONT_MAIN, bg=COLOR_BG).pack(side='left')

        # 3.5 格式转换 (WebP)
        row3 = tk.Frame(self.settings_frame, bg=COLOR_BG)
        row3.pack(fill='x', padx=10, pady=5)
        
        self.var_webp = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text="转换为 WebP 格式 (体积更小，画质更好)", variable=self.var_webp).pack(side='left')

        # 3.6 覆盖源文件
        self.var_overwrite = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text="覆盖源文件", variable=self.var_overwrite).pack(side='left', padx=15)

        # 4. 底部状态与按钮
        bottom_frame = tk.Frame(self, bg=COLOR_BG, pady=10)
        bottom_frame.pack(fill='x', side='bottom')
        
        self.progress = ttk.Progressbar(bottom_frame, orient='horizontal', length=300, mode='determinate')
        self.progress.pack(pady=5, padx=20, fill='x')
        
        self.lbl_status = tk.Label(bottom_frame, text="准备就绪", font=FONT_MAIN, bg=COLOR_BG, fg="#555")
        self.lbl_status.pack()

    def update_mode_ui(self):
        # 清空现有控件
        for widget in self.ctrl_frame.winfo_children():
            widget.destroy()
            
        mode = self.var_mode.get()
        
        if mode == "auto":
            tk.Label(self.ctrl_frame, text="最大文件大小:", font=FONT_MAIN, bg=COLOR_BG).pack(side='left')
            
            if not hasattr(self, 'var_kb'):
                self.var_kb = tk.IntVar(value=150)
                
            scale = ttk.Scale(self.ctrl_frame, from_=20, to=2000, orient='horizontal', variable=self.var_kb, 
                              command=lambda v: self.lbl_val.config(text=f"{int(float(v))} KB"))
            scale.pack(side='left', fill='x', expand=True, padx=10)
            
            self.lbl_val = tk.Label(self.ctrl_frame, text=f"{self.var_kb.get()} KB", font=FONT_BOLD, bg=COLOR_BG, width=8)
            self.lbl_val.pack(side='left')
            
        else: # fixed quality
            tk.Label(self.ctrl_frame, text="压缩质量(比例):", font=FONT_MAIN, bg=COLOR_BG).pack(side='left')
            
            if not hasattr(self, 'var_quality'):
                self.var_quality = tk.IntVar(value=85)
                
            scale = ttk.Scale(self.ctrl_frame, from_=10, to=100, orient='horizontal', variable=self.var_quality,
                              command=lambda v: self.lbl_val.config(text=f"{int(float(v))}%"))
            scale.pack(side='left', fill='x', expand=True, padx=10)
            
            self.lbl_val = tk.Label(self.ctrl_frame, text=f"{self.var_quality.get()}%", font=FONT_BOLD, bg=COLOR_BG, width=8)
            self.lbl_val.pack(side='left')

    def toggle_resize(self):
        if self.var_resize.get():
            self.combo_width['state'] = 'normal'
        else:
            self.combo_width['state'] = 'disabled'

    def on_click_select(self, event):
        files = filedialog.askopenfilenames(title="选择图片", filetypes=[("Files", "*.jpg *.jpeg *.png *.webp *.gif *.pdf")])
        if files:
            self.process_files(list(files))

    def on_drop(self, event):
        raw_data = event.data
        path_list = self.parse_drop_files(raw_data)
        self.process_files(path_list)

    def parse_drop_files(self, raw_data):
        # 使用 TkinterDnD 内置的 splitlist 方法处理路径
        # 它能正确处理带空格的路径（会被 {} 包裹的情况）
        try:
            return self.tk.splitlist(raw_data)
        except:
            # 兼容性备选方案
            if raw_data.startswith('{'):
                import re
                return re.findall(r'\{(.*?)\}', raw_data) or [raw_data.strip('{}')]
            return raw_data.split()

    def process_files(self, paths):
        # 1. 收集所有图片文件
        self.files_to_process = []
        # 扩展支持的格式
        supported = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff', '.jfif', '.gif', '.pdf')
        
        # 确保 paths 是列表
        if isinstance(paths, str):
            paths = [paths]

        for p in paths:
            # 移除可能存在的引号和处理 Windows 路径
            p = p.strip().strip('"').strip("'")
            if not p:
                continue
            
            p = os.path.normpath(p) # 标准化路径
            
            if os.path.isfile(p):
                if p.lower().endswith(supported):
                    self.files_to_process.append(p)
            elif os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for f in files:
                        if f.lower().endswith(supported):
                            full_path = os.path.normpath(os.path.join(root, f))
                            self.files_to_process.append(full_path)
                            
        # 去重
        self.files_to_process = list(dict.fromkeys(self.files_to_process))
                            
        if not self.files_to_process:
            messagebox.showwarning("提示", "未找到支持的图片文件！")
            return
            
        msg_dest = "输出目录将在源文件夹下的 '_compressed' 中。"
        if self.var_overwrite.get():
             msg_dest = "⚠️ 注意：将直接覆盖源文件！"
        
        confirm = messagebox.askyesno("确认", f"找到 {len(self.files_to_process)} 个文件。\n\n是否开始压缩？\n\n{msg_dest}")
        if confirm:
            self.start_compression_thread()

    def start_compression_thread(self):
        # 锁定界面
        self.lbl_drop.config(state='disabled', text="🚀 正在处理中，请稍候...")
        self.progress['value'] = 0
        self.progress['maximum'] = len(self.files_to_process)
        
        # 获取参数
        mode = self.var_mode.get()
        params = {
            'target_size_kb': self.var_kb.get() if mode == 'auto' else None,
            'quality': self.var_quality.get() if mode == 'fixed' else 95,
            'fixed_quality': (mode == 'fixed'),
            'max_width': int(self.combo_width.get()) if self.var_resize.get() else None,
            'to_webp': self.var_webp.get(),
            'overwrite': self.var_overwrite.get()
        }
        
        # 开启线程
        t = threading.Thread(target=self.run_process, args=(params,))
        t.start()
        
    def run_process(self, params):
        success_count = 0
        
        for i, file_path in enumerate(self.files_to_process):
            src_dir = os.path.dirname(file_path)
            out_dir = os.path.join(src_dir, "_compressed")
            
            # 回调更新进度
            self.update_progress(i, len(self.files_to_process), os.path.basename(file_path))
            
            try:
                # 覆盖逻辑判断
                overwrite = params.get('overwrite', False)
                if overwrite:
                    out_dir = src_dir
                else:
                    if not os.path.exists(out_dir):
                        os.makedirs(out_dir)
                
                name, ext = os.path.splitext(os.path.basename(file_path))
                
                # 保留原始后缀逻辑 (针对 PDF)
                is_pdf = (ext.lower() == '.pdf')
                is_gif = (ext.lower() == '.gif')
                
                if params['to_webp'] and not is_pdf: # PDF 不转 WebP
                    out_name = f"{name}.webp"
                elif is_gif and not params['to_webp']:
                     out_name = f"{name}.gif"
                elif is_pdf:
                     out_name = f"{name}.pdf"
                else:
                    out_name = f"{name}.jpg"
                
                out_path = os.path.join(out_dir, out_name)
                
                # 处理覆盖时的文件占用问题
                is_same_file = (os.path.normpath(file_path) == os.path.normpath(out_path))
                temp_path = None
                
                if is_same_file:
                    temp_path = out_path + ".tmp"
                    target_path = temp_path
                else:
                    target_path = out_path
                
                ok, msg, size = self.compressor.compress_image(
                    file_path, target_path, 
                    target_size_kb=params.get('target_size_kb'),
                    max_width=params.get('max_width'),
                    to_webp=params.get('to_webp'),
                    quality=params.get('quality'),
                    fixed_quality=params.get('fixed_quality')
                )
                
                if ok:
                    if is_same_file and temp_path:
                        # 压缩成功后替换原文件
                        try:
                            if os.path.exists(out_path):
                                os.remove(out_path)
                            os.rename(temp_path, out_path)
                        except Exception as e:
                            print(f"Error replacing file {out_path}: {e}")
                            msg = f"Error replacing: {e}"
                            ok = False
                    
                    success_count += 1
                
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                
        self.update_progress(len(self.files_to_process), len(self.files_to_process), "完成")
        self.completed(success_count)

    def update_progress(self, current, total, filename):
        self.after(0, lambda: self._update_ui_progress(current, total, filename))
        
    def _update_ui_progress(self, current, total, filename):
        self.progress['value'] = current
        self.lbl_status.config(text=f"正在处理 ({current}/{total}): {filename}")

    def completed(self, count):
        self.after(0, lambda: self._show_complete(count))

    def _show_complete(self, count):
        self.lbl_drop.config(state='normal', text="👇 请将图片或文件夹拖入此处 👇\n\n(支持 JPG, PNG, WebP, GIF, PDF)")
        self.lbl_status.config(text=f"处理完成！成功压缩 {count} 个文件。")
        
        msg_dest = "文件已保存至各源文件夹下的 '_compressed' 目录中。"
        if self.var_overwrite.get():
             msg_dest = "源文件已成功被覆盖/更新。"
             
        messagebox.showinfo("完成", f"已完成！\n成功: {count}\n\n{msg_dest}")

if __name__ == "__main__":
    try:
        app = CompressionToolApp()
        app.mainloop()
    except Exception as e:
        messagebox.showerror("启动错误", f"程序启动失败:\n{e}")
