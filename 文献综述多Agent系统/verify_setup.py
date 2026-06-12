#!/usr/bin/env python3
"""系统验证脚本 - 检查环境和依赖是否正确配置"""

import sys
import os
import importlib

def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"[FAIL] Python 版本过低: {version.major}.{version.minor}")
        print("       需要 Python 3.8 或更高版本")
        return False
    print(f"[OK] Python 版本: {version.major}.{version.minor}.{version.micro}")
    return True

def check_dependencies():
    """检查依赖包"""
    required = ['requests', 'yaml']
    optional = ['openai']
    all_ok = True

    print("\n检查必需依赖:")
    for pkg in required:
        try:
            importlib.import_module(pkg)
            print(f"  [OK] {pkg}")
        except ImportError:
            print(f"  [FAIL] {pkg} - 请运行: pip install {pkg}")
            all_ok = False

    print("\n检查可选依赖:")
    for pkg in optional:
        try:
            importlib.import_module(pkg)
            print(f"  [OK] {pkg}")
        except ImportError:
            print(f"  [WARN] {pkg} - 可选，用于某些提供商")

    return all_ok

def check_project_structure():
    """检查项目文件结构"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    required_files = [
        'main.py',
        'config.py',
        'agents/__init__.py',
        'agents/base.py',
        'agents/coordinator.py',
        'agents/searcher.py',
        'agents/analyzer.py',
        'agents/organizer.py',
        'agents/writer.py',
        'agents/reviewer.py',
        'llm/client.py',
        'tools/paper_search.py',
        'errors.py',
        'progress.py',
        'pipeline.py',
    ]

    print("\n检查项目文件:")
    all_ok = True
    for file in required_files:
        path = os.path.join(base_dir, file)
        if os.path.exists(path):
            print(f"  [OK] {file}")
        else:
            print(f"  [FAIL] {file} - 文件缺失")
            all_ok = False

    return all_ok

def check_api_key():
    """检查 API Key 配置"""
    print("\n检查 API Key 配置:")

    providers = {
        'DeepSeek': 'DEEPSEEK_API_KEY',
        'OpenAI': 'OPENAI_API_KEY',
        '智谱': 'ZHIPU_API_KEY',
        '通义': 'QWEN_API_KEY',
        '通用': 'LLM_API_KEY',
    }

    found_any = False
    for name, env_var in providers.items():
        key = os.environ.get(env_var)
        if key:
            masked = key[:8] + '...' if len(key) > 8 else key
            print(f"  [OK] {name}: {masked}")
            found_any = True

    if not found_any:
        print("  [WARN] 未找到 API Key 环境变量")
        print("         请设置其中一个，或使用 --api-key 参数")
        print("         示例: export DEEPSEEK_API_KEY=sk-your-key-here")

    return found_any

def main():
    """主验证函数"""
    print("=" * 60)
    print("  文献综述系统 - 环境验证")
    print("=" * 60)

    results = []

    # 1. Python 版本
    print("\n[1/4] 检查 Python 版本...")
    results.append(check_python_version())

    # 2. 依赖包
    print("\n[2/4] 检查依赖包...")
    results.append(check_dependencies())

    # 3. 项目结构
    print("\n[3/4] 检查项目文件...")
    results.append(check_project_structure())

    # 4. API Key
    print("\n[4/4] 检查 API Key...")
    results.append(check_api_key())

    # 总结
    print("\n" + "=" * 60)
    if all(results[:3]):  # 前三项必须通过
        print("  [PASS] 环境验证通过！")
        print("\n  下一步：")
        if results[3]:
            print("  1. 运行: python main.py --topic \"你的研究主题\"")
        else:
            print("  1. 设置 API Key: export DEEPSEEK_API_KEY=sk-your-key")
            print("  2. 运行: python main.py --topic \"你的研究主题\"")
    else:
        print("  [FAIL] 环境验证失败")
        print("\n  请修复上述 [FAIL] 项后重试")
    print("=" * 60)

    return 0 if all(results[:3]) else 1

if __name__ == "__main__":
    sys.exit(main())
