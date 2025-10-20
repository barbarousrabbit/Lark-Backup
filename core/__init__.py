"""
核心功能模块包
"""
# 添加父目录到系统路径，避免在每个模块中重复
import os
import sys

# 只有当作为包导入时才添加父目录到系统路径
if __name__ != "__main__":
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir) 