# 快速启动指南

## 系统要求

- Python 3.8 或更高版本
- 稳定的网络连接（用于 API 调用）
- DeepSeek API Key（或其他 LLM 提供商的 key）

## 第一步：获取 API Key

### DeepSeek（推荐，性价比高）
1. 访问 https://platform.deepseek.com/
2. 注册账号
3. 在 API Keys 页面创建新的 API Key
4. 复制保存（格式：sk-xxxxxxxx）

### 其他提供商
- OpenAI: https://platform.openai.com/api-keys
- 智谱: https://open.bigmodel.cn/
- 通义: https://dashscope.aliyun.com/

## 第二步：安装依赖

打开终端/命令提示符，运行：

```bash
cd "c:\Users\Administrator\Desktop\Claude Project\GitHub开源项目\文献综述多Agent系统"
pip install -r requirements.txt
```

如果网络慢，可以使用国内镜像：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 第三步：设置 API Key

### Windows PowerShell
```powershell
$env:DEEPSEEK_API_KEY="sk-your-key-here"
```

### Windows CMD
```cmd
set DEEPSEEK_API_KEY=sk-your-key-here
```

### Linux/Mac
```bash
export DEEPSEEK_API_KEY=sk-your-key-here
```

## 第四步：运行系统

### 基础运行
```bash
python main.py --topic "你的研究主题"
```

### 完整示例
```bash
python main.py \
  --topic "深度学习在医学影像中的应用" \
  --extra "重点关注2020年后的最新进展，包括CNN、Transformer等方法" \
  --workers 4 \
  --provider deepseek
```

### 使用其他提供商

#### OpenAI
```bash
export OPENAI_API_KEY=sk-your-key-here
python main.py --topic "主题" --provider openai --model gpt-4o
```

#### 智谱
```bash
export ZHIPU_API_KEY=your-key-here
python main.py --topic "主题" --provider zhipu
```

#### 本地 Ollama
```bash
python main.py --topic "主题" --provider ollama --model qwen2.5:14b
```

## 命令行参数说明

| 参数 | 缩写 | 说明 | 示例 |
|------|------|------|------|
| `--topic` | `-t` | 研究主题（必需） | `"深度学习"` |
| `--extra` | `-e` | 额外约束或关注点 | `"2020年后"` |
| `--api-key` | | API Key | `sk-xxx` |
| `--provider` | `-p` | LLM 提供商 | `deepseek` |
| `--model` | `-m` | 模型名称 | `deepseek-chat` |
| `--workers` | `-w` | 并行线程数 | `4` |
| `--sequential` | `-s` | 强制顺序执行 | |
| `--config-file` | `-c` | 配置文件路径 | `config.yml` |

## 输出文件

运行完成后，在 `output/` 目录下生成：

```
output/
├── 01_plan.json          # 调研计划
├── 02_papers.json        # 检索到的论文
├── 03_analyses.json      # 逐篇分析
├── 04_organized.json     # 聚类与研究空白
├── 05_draft.md           # 综述初稿
├── 06_review.json        # 审校意见
└── 07_final_survey.md    # 最终综述（主输出）
```

## 常见问题

### Q1: 提示 "API Key 未设置"
**解决方案**：确保正确设置了环境变量，或使用 `--api-key` 参数

### Q2: 提示 "模块未找到"
**解决方案**：
```bash
pip install -r requirements.txt
```

### Q3: 网络超时
**解决方案**：
- 检查网络连接
- 使用代理（如需要）
- 减少并行线程数：`--workers 2`

### Q4: 返回空结果
**解决方案**：
- 尝试更宽泛的主题关键词
- 检查 API Key 是否有效
- 查看 `output/02_papers.json` 确认是否检索到论文

## 性能优化建议

1. **并行执行**：默认 4 线程，可根据网络情况调整
   ```bash
   python main.py -t "主题" -w 8  # 更多线程
   python main.py -t "主题" -s    # 顺序执行（网络差时）
   ```

2. **选择合适的提供商**：
   - DeepSeek：性价比高，中文支持好
   - OpenAI：质量高，但贵
   - 本地 Ollama：免费，但需要本地 GPU

3. **配置文件**：重复使用时创建 `litreview.yml`
   ```yaml
   llm:
     provider: deepseek
     api_key: sk-xxx
   search:
     max_results: 10
   workers: 4
   ```

## 示例输出

运行后会看到类似输出：

```
============================================================
  文献综述自动梳理系统
============================================================

[1/6] 协调员制定调研计划...
     计划完成：5 个子方向，6 个章节

[2/6] 搜索员检索论文...
     筛选相关论文...
     最终保留 25 篇

[3/6] 分析员深度分析论文...
     [████████████░░░░░░░░] 3/5 (60%)
     分析完成：25 篇

[4/6] 组织员聚类分类...
     聚类完成：4 个类别

[5/6] 撰稿人撰写综述...
     初稿完成：output/05_draft.md

[6/6] 审校员质量检查...
     评分: 8/10

============================================================
  综述生成完成！
============================================================

输出文件:
  综述全文: output/07_final_survey.md
  论文分析: output/03_analyses.json
  聚类结果: output/04_organized.json

共检索 45 篇论文，分析 25 篇，聚类 4 个类别，识别 3 个研究空白。
```

## 获取帮助

```bash
python main.py --help
```

## 技术支持

如遇到问题，请检查：
1. Python 版本是否符合要求
2. 依赖是否完整安装
3. API Key 是否有效
4. 网络连接是否正常
