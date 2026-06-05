# SlideWise — 开发计划与决策记录

> 计算机图形学 PJ3：Agent驱动的PPT自动生成工具  
> DDL：6月10日 23:59

---

## 一、架构决策（已确认）

| # | 决策 | 结论 |
|---|------|------|
| D1 | 基础引擎 | 复用 ppt-master 的 SVG→PPTX 编译管线、图标库、图表模板，**不重写轮子** |
| D2 | 项目结构 | 新建独立项目 `slidewise/`，从 ppt-master 中**拷贝**所需代码，不使用原项目架构 |
| D3 | Agent 数量 | **3个Agent**：Strategist（内容分析+大纲）→ Generator（逐页SVG）→ Reviewer（排版审查） |
| D4 | 文本溢出检测 | **双层方案**：Reviewer Agent 静态规则检测 + Python PIL 精确像素测量 |
| D5 | 风格系统 | Guizang 瑞士国际主义（4套调色板、5级字体、16列网格、禁止圆角阴影） |
| D6 | 交互形态 | 独立 Web 应用：FastAPI + WebSocket + 单HTML前端 |
| D7 | LLM 选型 | DeepSeek V4 Flash（OpenAI 兼容 API，100万token上下文） |
| D8 | 布局方式 | 7种预定义布局模板（L1-L7），LLM在模板内填充，不从零设计 |

---

## 二、项目结构

```
slidewise/
├── main.py                    # FastAPI 入口，启动 WebSocket 服务
├── requirements.txt           # Python 依赖
├── .env.example               # API Key 配置模板
├── agents/
│   ├── __init__.py
│   ├── base.py                # Agent 基类（DeepSeek API 调用封装）
│   ├── strategist.py          # Strategist Agent：内容分析 + 大纲规划
│   ├── generator.py           # Generator Agent：逐页 SVG 生成
│   └── reviewer.py            # Reviewer Agent：排版审查 + 文本溢出检测
├── engine/
│   ├── __init__.py
│   ├── svg_to_pptx/           # ← ppt-master：SVG→DrawingML 编译器
│   ├── svg_finalize/          # ← ppt-master：SVG 后处理
│   ├── source_to_md/          # ← ppt-master：文档转换
│   ├── finalize_svg.py        # ← ppt-master：后处理入口
│   ├── total_md_split.py      # ← ppt-master：备注分割
│   └── text_measurer.py       # NEW：PIL 文本精确测量
├── templates/
│   ├── icons/                 # ← ppt-master：640+ 矢量图标
│   └── charts/                # ← ppt-master：图表模板
├── constraints/
│   ├── __init__.py
│   ├── guizang.py             # Guizang 风格约束定义
│   └── validator.py           # 程序化约束验证器
├── protocols/
│   ├── __init__.py
│   └── websocket.py           # WebSocket 消息类型定义
├── sessions/
│   ├── __init__.py
│   └── manager.py             # 会话生命周期管理
├── frontend/
│   └── index.html             # 单HTML前端（聊天面板+预览网格）
└── outputs/                   # 生成的 PPTX 输出目录
```

---

## 三、3-Agent 流水线

```
源文档 (PDF/MD/文本)
       │
       ▼
[Strategist Agent]           ← 内容分析 + 大纲规划
   输出: outline JSON
       │
   🛑 用户确认大纲
       │
       ▼
[Generator Agent]            ← 逐页 SVG 生成（7种布局模板）
   输出: slides SVG[]
       │
       ▼
[Reviewer Agent]             ← 4维度审查 + 文本溢出检测
   输出: issues[]
       │
   🛑 用户决定修复/忽略
       │
       ▼ (有修复需求时回到 Generator)
[Generator Agent] (修复模式)  ← 仅修复标记页
       │
       ▼
[最终编译]                    ← finalize_svg + svg_to_pptx
   输出: output.pptx
```

---

## 四、Implementation Steps

### Step 1: 项目基础搭建
- [x] 1.1 创建 `requirements.txt`
- [x] 1.2 创建 `.env.example`
- [x] 1.3 创建各目录的 `__init__.py`

### Step 2: 从 ppt-master 拷贝引擎代码
- [x] 2.1 拷贝 `svg_to_pptx/` 编译器（DrawingML 转换核心）
- [x] 2.2 拷贝 `svg_finalize/` 后处理模块
- [x] 2.3 拷贝 `source_to_md/` 文档转换
- [x] 2.4 拷贝 `finalize_svg.py`、`total_md_split.py`
- [x] 2.5 拷贝 `templates/icons/`、`templates/charts/`
- [x] 2.6 拷贝 `config.py`、`project_utils.py`
- [x] 2.7 调整所有拷贝代码的 import 路径适配新项目（经验证无需修改，`finalize_svg.py` 已有 `sys.path.insert`）

### Step 3: Guizang 约束系统
- [x] 3.1 `constraints/guizang.py`：4套调色板、5级字体层级、7种布局模板定义
- [x] 3.2 `constraints/validator.py`：程序化约束验证（调色板检查、字号比例检查、栅格对齐检查）

### Step 4: 文本测量引擎
- [x] 4.1 `engine/text_measurer.py`：基于 PIL ImageFont 的精确文本宽度计算
- [x] 4.2 文本溢出检测算法（文本宽度 vs 容器宽度）
- [x] 4.3 字体层级比例验证（H1:Body ≥ 8:1）

### Step 5: Agent 层实现
- [x] 5.1 `agents/base.py`：DeepSeek API 调用封装、重试、JSON解析
- [x] 5.2 `agents/strategist.py`：System Prompt + 大纲规划逻辑
- [x] 5.3 `agents/generator.py`：System Prompt + 逐页SVG生成 + 修复模式
- [x] 5.4 `agents/reviewer.py`：System Prompt + 4维度审查 + 文本溢出规则

### Step 6: 后端服务
- [x] 6.1 `protocols/websocket.py`：6种消息类型定义
- [x] 6.2 `sessions/manager.py`：会话生命周期管理
- [x] 6.3 `main.py`：FastAPI + WebSocket + 静态文件 + Agent 调度

### Step 7: 前端
- [x] 7.1 `frontend/index.html`：两栏布局 + 聊天面板 + 预览网格
- [x] 7.2 WebSocket 客户端 + 状态管理
- [x] 7.3 文件拖拽上传 + 大纲编辑 + 评审卡片交互

### Step 8: 集成测试与报告
- [ ] 8.1 端到端流程联调
- [ ] 8.2 撰写 ICLR 格式报告（英文）
- [ ] 8.3 制作汇报 PPT

---

## 五、已确认的技术方案细节

### 文本溢出检测（双层方案）

**层A — Reviewer Agent 静态规则**：
- 解析 SVG 源码中每个 `<text>` 元素
- 估算公式：中文 ≈ 字号×字数×1.1, 英文 ≈ 字号×字数×0.55
- 与父容器宽度对比，溢出 >10% 报 error, 5-10% 报 warning

**层B — Python PIL 精确测量**：
- `ImageFont.getbbox(text)` 获取精确像素宽度
- 在 `finalize_svg` 前执行，生成文本溢出报告
- 超标页自动标记，反馈给用户

### WebSocket 消息协议

**服务端 → 客户端**：
```json
{"type": "outline", "data": {"pages": [...]}}
{"type": "slide_generated", "data": {"index": 3, "svg": "..."}}
{"type": "review_report", "data": {"issues": [...], "summary": "..."}}
{"type": "slide_fixed", "data": {"index": 3, "svg": "..."}}
{"type": "done", "data": {"download_url": "/download/abc123"}}
{"type": "error", "data": {"message": "..."}}
```

**客户端 → 服务端**：
```json
{"type": "user_message", "data": {"text": "...", "files": ["base64..."]}}
{"type": "confirm_outline", "data": {"approved": true, "modified_outline": [...]}}
{"type": "fix_decisions", "data": {"fix": [3, 5], "ignore": [2], "feedback": "..."}}
{"type": "retry_slide", "data": {"index": 5, "feedback": "..."}}
{"type": "download", "data": {}}
```
