#!/usr/bin/env python3
"""
RAG 本地检索系统 - 安装/初始化脚本

使用方法:
    # 方式 1: 下载并运行
    curl -sSL https://raw.githubusercontent.com/your-repo/rag-install.py | python3
    
    # 方式 2: 本地运行
    python3 rag_install.py
    
    # 方式 3: 指定目标目录
    python3 rag_install.py /path/to/your/project

功能:
    1. 检查/创建 conda 环境 (rag-env, Python 3.11)
    2. 安装依赖 (sentence-transformers, numpy)
    3. 复制 RAG 核心代码到目标项目
    4. 创建启动脚本
    5. 更新 .gitignore
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# ============================================================
# 启动脚本模板
# ============================================================

LAUNCHER_SCRIPT = '''#!/bin/bash
# RAG 本地检索工具
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 尝试寻找 conda
if command -v conda &> /dev/null; then
    CONDA_CMD="conda"
elif [ -f "/usr/local/Caskroom/miniforge/base/bin/conda" ]; then
    CONDA_CMD="/usr/local/Caskroom/miniforge/base/bin/conda"
elif [ -f "$HOME/miniforge3/bin/conda" ]; then
    CONDA_CMD="$HOME/miniforge3/bin/conda"
elif [ -f "$HOME/miniconda3/bin/conda" ]; then
    CONDA_CMD="$HOME/miniconda3/bin/conda"
else
    echo "❌ 未找到 conda 命令，请确保已安装 conda/miniforge"
    exit 1
fi

cd "$SCRIPT_DIR"
# 使用 conda run 执行，避免硬编码 python 绝对路径
exec "$CONDA_CMD" run -n rag-env python rag_search.py "$@"
'''

# ============================================================
# 安装逻辑
# ============================================================

def run_cmd(cmd, check=True, capture=False):
    """运行命令"""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if check and result.returncode != 0:
        print(f"  ❌ 命令失败: {result.stderr if capture else ''}")
        return None
    return result

def check_conda():
    """检查 conda 是否安装"""
    result = subprocess.run(["which", "conda"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    
    # 检查 miniforge
    miniforge_path = "/usr/local/Caskroom/miniforge/base/bin/conda"
    if os.path.exists(miniforge_path):
        return miniforge_path
    
    return None

def setup_conda_env():
    """设置 conda 环境"""
    conda_path = check_conda()
    
    if not conda_path:
        print("\n❌ 未找到 conda，请先安装 miniforge:")
        print("   brew install --cask miniforge")
        print("   然后重新运行此脚本")
        return False
    
    print(f"\n✅ 找到 conda: {conda_path}")
    
    # 检查 rag-env 是否存在
    result = subprocess.run(
        [conda_path, "env", "list"],
        capture_output=True, text=True
    )
    
    if "rag-env" in result.stdout:
        print("✅ rag-env 环境已存在")
    else:
        print("\n📦 创建 rag-env 环境 (Python 3.11)...")
        subprocess.run([conda_path, "create", "-n", "rag-env", "python=3.11", "-y"])
    
    # 安装依赖
    env_python = "/usr/local/Caskroom/miniforge/base/envs/rag-env/bin/pip"
    if os.path.exists(env_python):
        print("\n📦 安装依赖...")
        subprocess.run([env_python, "install", "sentence-transformers", "numpy", "-q"])
        print("✅ 依赖安装完成")
    
    return True

def install_rag_files(target_dir: Path):
    """安装 RAG 文件到目标目录"""
    target_dir = Path(target_dir).resolve()
    source_dir = Path(__file__).parent.resolve()
    
    print(f"\n📁 安装 RAG 到: {target_dir}")
    
    # 复制核心文件
    for filename in ["rag_indexer.py", "rag_search.py"]:
        src_file = source_dir / filename
        dst_file = target_dir / filename
        if src_file.exists():
            if src_file != dst_file:
                shutil.copy2(src_file, dst_file)
            print(f"  ✅ 复制: {filename}")
        else:
            print(f"  ❌ 找不到源文件: {src_file}")
    
    # 创建启动脚本
    launcher_path = target_dir / "rag"
    launcher_path.write_text(LAUNCHER_SCRIPT.strip() + "\n")
    os.chmod(launcher_path, 0o755)
    print("  ✅ 创建: rag (启动脚本)")
    
    # 更新 .gitignore
    gitignore = target_dir / ".gitignore"
    ignore_entry = ".rag_index/"
    
    if gitignore.exists():
        content = gitignore.read_text()
        if ignore_entry not in content:
            with open(gitignore, "a") as f:
                f.write(f"\n# RAG 索引缓存\n{ignore_entry}\n")
            print("  ✅ 更新: .gitignore")
    else:
        gitignore.write_text(f"# RAG 索引缓存\n{ignore_entry}\n")
        print("  ✅ 创建: .gitignore")

def main():
    print("=" * 60)
    print("🚀 RAG 本地检索系统 - 安装程序")
    print("=" * 60)
    
    # 确定目标目录
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1])
    else:
        target_dir = Path.cwd()
    
    print(f"\n目标目录: {target_dir}")
    
    # 1. 设置 conda 环境
    if not setup_conda_env():
        sys.exit(1)
    
    # 2. 安装文件
    install_rag_files(target_dir)
    
    # 完成
    print("\n" + "=" * 60)
    print("✅ 安装完成！")
    print("=" * 60)
    print("\n使用方法:")
    print(f"  cd {target_dir}")
    print("  ./rag")
    print("\n首次运行会自动构建索引（约 1-2 分钟）")
    print("之后使用 'update' 命令进行增量更新")
    print("=" * 60)

if __name__ == "__main__":
    main()
