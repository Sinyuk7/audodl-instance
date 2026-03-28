import os
import time

# ================= 配置区 =================
SCAN_DIR = '/root/autodl-tmp'
FILE_THRESHOLD = 100 * 1024 * 1024      # 大文件阈值：100MB
FOLDER_THRESHOLD = 1 * 1024 * 1024 * 1024 # 大文件夹阈值：1GB
LOG_FILE = 'disk_scan_log.txt'          # 完整日志输出路径

# 空间杀手重点关照名单
MODEL_EXTS = {'.safetensors', '.ckpt', '.pth', '.bin', '.pt', '.onnx', '.gguf'}
TARGET_DIRS = {'huggingface', '.cache', 'pip', 'conda', 'pkgs', 'custom_nodes', 'outputs', 'wandb'}
# ==========================================

large_files = []   # 存储 (size, path)
large_folders = [] # 存储 (size, path)

# 统计杀手数据
killer_models_size = {ext: 0 for ext in MODEL_EXTS}
killer_dirs_size = {d: 0 for d in TARGET_DIRS}

def format_size(size_bytes):
    """字节转换可视化"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0

def scan_directory(path):
    """使用高效的 os.scandir 递归扫描，自底向上累计文件夹大小"""
    total_size = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                # 跳过软链接，防止死循环或算错挂载盘
                if entry.is_symlink():
                    continue
                
                if entry.is_file():
                    try:
                        size = entry.stat().st_size
                        total_size += size
                        
                        # 记录大文件
                        if size >= FILE_THRESHOLD:
                            large_files.append((size, entry.path))
                            
                        # 统计模型权重碎片
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in MODEL_EXTS:
                            killer_models_size[ext] += size
                            
                    except OSError:
                        pass
                
                elif entry.is_dir():
                    # 递归计算子目录
                    dir_size = scan_directory(entry.path)
                    total_size += dir_size
                    
                    # 记录特定缓存和产物目录的总大小
                    if entry.name in TARGET_DIRS:
                        killer_dirs_size[entry.name] += dir_size
                        
    except (PermissionError, FileNotFoundError):
        pass # 忽略无权限或扫描中途被删除的文件/目录

    # 记录大文件夹
    if total_size >= FOLDER_THRESHOLD:
        large_folders.append((total_size, path))
        
    return total_size

def main():
    print(f"🚀 开始全速扫描 [{SCAN_DIR}] ...")
    start_time = time.time()
    
    total_used = scan_directory(SCAN_DIR)
    
    # 按大小降序排序
    large_files.sort(key=lambda x: x[0], reverse=True)
    large_folders.sort(key=lambda x: x[0], reverse=True)
    
    # --- 1. 终端输出 Top 10 & 杀手统计 ---
    print(f"\n✅ 扫描完成！耗时: {time.time() - start_time:.2f} 秒. 目录总占用: {format_size(total_used)}\n")
    
    print("🔥 [空间杀手 - 常见环境与产物目录]")
    for d, size in sorted(killer_dirs_size.items(), key=lambda x: x[1], reverse=True):
        if size > 0: print(f"  - {d.ljust(15)} : {format_size(size)}")

    print("\n📦 [空间杀手 - 模型权重文件总计]")
    for ext, size in sorted(killer_models_size.items(), key=lambda x: x[1], reverse=True):
        if size > 0: print(f"  - {ext.ljust(15)} : {format_size(size)}")

    print(f"\n📂 Top 10 巨无霸文件夹 (>{format_size(FOLDER_THRESHOLD)})")
    for size, path in large_folders[:10]:
        print(f"  [{format_size(size).rjust(10)}] {path}")

    print(f"\n📄 Top 10 巨无霸文件 (>{format_size(FILE_THRESHOLD)})")
    for size, path in large_files[:10]:
        print(f"  [{format_size(size).rjust(10)}] {path}")

    # --- 2. 写入完整日志文件 ---
    print(f"\n📝 正在将全量数据写入日志文件: {LOG_FILE} ...")
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"扫描目录: {SCAN_DIR} | 总占用: {format_size(total_used)}\n")
        f.write("="*50 + "\n")
        
        f.write(f"--- 所有大于 {format_size(FOLDER_THRESHOLD)} 的文件夹 ---\n")
        for size, path in large_folders:
            f.write(f"[{format_size(size).rjust(10)}] {path}\n")
            
        f.write("\n" + "="*50 + "\n")
        f.write(f"--- 所有大于 {format_size(FILE_THRESHOLD)} 的文件 ---\n")
        for size, path in large_files:
            f.write(f"[{format_size(size).rjust(10)}] {path}\n")

    print("🎉 搞定！可以去查看日志文件慢慢清理了。")

if __name__ == '__main__':
    main()