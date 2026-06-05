# SlideWise — 项目设计文档

> 计算机图形学 Project 3：生成式AI实践
> Agent驱动的PPT自动生成工具

---

## 一、项目背景与目标

### 1.1 我们要做什么

**SlideWise** 是一个基于AI Agent的PPT自动生成工具。你只需要在浏览器里说一句话（比如"帮我把这篇论文转成组会PPT，靛蓝色，8页"），它就能自动生成一份排版精美、风格统一的 `.pptx` 文件。生成的PPT可以在PowerPoint/WPS里自由编辑——每个文本框、每个形状都是原生对象，不是死图片。

### 1.2 解决什么问题

作为计算机专业学生，我们经常遇到三种场景：

| 场景 | 痛点 | SlideWise怎么做 |
|------|------|----------------|
| **组会汇报** | 读了论文要快速出PPT | 拖入PDF → 自动提取要点 → 生成汇报PPT |
| **水课作业** | 不想花时间做PPT | 输入主题名 → 一键生成，点确认就完事 |
| **学习分享** | 有笔记大纲想做成PPT | 粘贴大纲 → 自动丰富内容 → 输出排版好的PPT |

### 1.3 课程契合点

本项目对应课程Project 3（生成式AI实践），核心主题是 **Agent + 图形学**。我们的创新点：

1. **双Agent质量循环**：生成Agent出初稿 → 评审Agent审查合规性 → 生成Agent修复，形成自动化的质量提升闭环
2. **约束驱动的设计系统**：将Guizang PPT的美学规则编码为可验证的设计约束，而非模糊的"做得好看点"
3. **SVG→PPTX编译管线**：借鉴PPT Master的做法，让LLM生成SVG代码，再通过python-pptx编译为原生PowerPoint对象——保证输出的真正可编辑性

---

## 二、整体架构

### 2.1 一句话概括

**一个浏览器聊天面板 + 一个Python后端 + 两个DeepSeek Agent + python-pptx编译 = 可编辑的高质量PPT**

### 2.2 系统架构图

```
┌─────────────────────────────────────────┐
│            浏览器（单HTML文件）            │
│     ┌──────────┐    ┌────────────────┐   │
│     │ 对话面板  │    │  幻灯片预览网格  │   │
│     │ (聊天驱动) │    │  (实时流式展示)  │   │
│     └─────┬────┘    └───────┬────────┘   │
│           │         WebSocket            │
└───────────┼───────────────┼──────────────┘
            │               │
            ▼               ▼
┌───────────────────────────────────────────┐
│           Python 后端 (FastAPI)            │
│                                           │
│  ┌─────────────────┐  ┌────────────────┐  │
│  │ Agent·生成       │  │ Agent·评审      │  │
│  │ (DeepSeek Flash) │  │ (DeepSeek Flash)│  │
│  │                  │  │                │  │
│  │ 理解输入→规划大纲 │  │ 审查SVG源码    │  │
│  │ →生成逐页SVG     │  │ →输出问题清单   │  │
│  │ →根据反馈修复    │  │ (4个维度检查)  │  │
│  └────────┬────────┘  └───────┬────────┘  │
│           │                   │            │
│           └──────┬────────────┘            │
│                  ▼                         │
│   ┌──────────────────────────────┐        │
│   │ SVG→PPTX 编译器 (python-pptx)│        │
│   │ BeautifulSoup解析SVG DOM     │        │
│   │ → 1:1映射到DrawingML对象     │        │
│   │ → 输出原生.pptx              │        │
│   └──────────────────────────────┘        │
└───────────────────────────────────────────┘
```

### 2.3 一次完整的生成流程

```
用户: "帮我把这篇论文转成组会PPT，靛蓝色，8页"
  │   [拖入 paper.pdf]
  │
  ▼
Agent·生成 → 解析论文 → 输出大纲JSON
  │
  ├─ 🛑 用户检查大纲：可以编辑标题、增减页、拆分合并
  │    用户："把方法拆成两页，去掉封面作者信息"
  │
  ▼
Agent·生成 → 逐页生成SVG（右侧网格实时出现缩略图）
  │
  ▼
Agent·评审 → 审查全部SVG源码 → 输出问题清单
  │    ⚠ 第3页：文字密度78%，超过65%阈值
  │    ⚠ 第5页：锚点色不一致
  │    ✓ 其他页面通过
  │
  ├─ 🛑 用户查看问题："都修复一下，另外第5页改用对比布局"
  │
  ▼
Agent·生成 → 修复第3、5页 → 只改问题页，其余不动
  │
  ├─ 🛑 用户验收："第3页OK，第5页左右比例调整一下再修一次"
  │
  ▼
Agent·生成 → 修复第5页 → 用户确认 ✓
  │
  ▼
python-pptx编译 → [下载 output.pptx]
```

**三个用户介入点**全部在浏览器聊天面板内完成，不需要切回终端。对于水课场景（"随便搞一下"），用户可以一路点"确认"跳过，一分钟出结果。

---

## 三、双Agent设计（核心创新）

两个Agent都使用 **DeepSeek V4 Flash**（上下文100万token，代码生成能力LiveCodeBench 91.6分，中文SuperCLUE国内第二，速度75 tok/s）。角色分离完全通过System Prompt实现，不需要切换模型。

### 3.1 Agent·生成（Generator）

**角色定位**：资深演示文稿设计师，擅长瑞士国际主义风格

**做什么**：
- 理解用户输入（自然语言 + 上传文件）
- 规划PPT大纲（每页标题、布局模板、页数）
- 逐页生成SVG代码（每页是完整的SVG文件）
- 接收评审报告和用户反馈，修复指定页面

**System Prompt核心**：
- 角色：瑞士国际主义风格演示文稿设计师
- 输出格式：严格JSON（outline + slides数组）
- SVG必须遵循Guizang设计约束（调色板、网格、字号层级等）
- 修复模式下只改被标记的页，不动其他页
- 用户的自然语言反馈视为新增约束

**输出JSON格式**：
```json
{
  "outline": [
    {"index": 1, "title": "封面: Transformer架构详解", "layout": "L1"},
    {"index": 2, "title": "背景: 注意力机制起源", "layout": "L3"}
  ],
  "slides": [
    {
      "index": 1,
      "layout": "L1",
      "svg": "<svg xmlns='...' viewBox='0 0 1920 1080'>...</svg>"
    }
  ]
}
```

### 3.2 Agent·评审（Reviewer）

**角色定位**：演示文稿设计审计员，质量守门人

**做什么**：
- 审查全部页面的SVG源码
- 从四个维度检查问题
- 输出结构化的问题清单（每页、每条、严重程度、修改建议）

**四个检查维度**：

| 维度 | 检查什么 | 示例 |
|------|---------|------|
| **style 风格合规** | 调色板是否超限、字号比≥8:1是否满足、是否出现禁止的圆角/阴影/渐变、是否用了纯白纯黑 | "第5页出现了#FFFFFF，Guizang规范禁止纯白" |
| **layout 排版质量** | 元素是否溢出、网格是否对齐、文字密度是否>65%、是否有孤立元素 | "第3页文字密度78%，建议精简或拆分" |
| **content 内容逻辑** | 标题是否准确概括内容、前后页数据是否矛盾、要点是否冗余 | "第4页标题说'实验结果'但内容是方法描述" |
| **hierarchy 信息层次** | 每页是否有明确的主次信息、是否违反呼吸节奏（连续三页不能同布局） | "第6-8页连续使用相同布局，违反呼吸节奏" |

**输出JSON格式**：
```json
{
  "issues": [
    {
      "page": 3,
      "severity": "error",
      "category": "layout",
      "description": "Text density 78%, exceeds 65% threshold",
      "suggestion": "Split paragraph 2 into a new slide, or reduce to 3 bullet points"
    }
  ],
  "summary": "Checked 8 pages. Found 2 errors, 3 warnings, 1 suggestion."
}
```

### 3.3 两个Agent如何协作

```
评审Agent → 生成Agent:
  severity=error   → 必须修复（自动）
  severity=warning → 用户决定是否修复
  severity=suggestion → 默认忽略，除非用户明确要求

用户 → 生成Agent:
  自然语言反馈 → 附加到下一轮生成Agent的上下文
  每轮保留所有之前的约束，累加新约束
```

**设计理念**：评审Agent只做"发现问题和提建议"，生成Agent做"修改"。两个角色之间不直接对话——评审报告通过用户界面展示，用户做最终决策。这保证了：
- 用户始终有控制权
- 评审和生成各司其职，不存在"互相妥协"
- 同一模型但不同角色，通过System Prompt隔离认知盲区

---

## 四、风格系统（Guizang瑞士国际主义）

风格系统借鉴 [Guizang PPT Skill](https://github.com/op7418/guizang-ppt-skill) 的B风格（瑞士国际主义）。核心哲学是**"约束驱动设计"**——限制AI的自由度比给AI自由更重要。所有约束都嵌入生成Agent的System Prompt，并由评审Agent自动验证。

### 4.1 四套调色板

每份PPT严格使用一个色系，不允许跨色系混用。

| 主题 | 背景色 | 文字色 | 锚点色 | 适用场景 |
|------|--------|--------|--------|---------|
| **靛蓝 Indigo**（默认） | `#0a1f3d` | `#f1f3f5` | `#4a90d9` | 技术、AI、组会 |
| **墨水 Ink** | `#0a0a0b` | `#f1efea` | `#c9a96e` | 通用、正式 |
| **森林 Forest** | `#1a2e1f` | `#f5f1e8` | `#7a9a6e` | 自然、跨学科 |
| **沙丘 Dune** | `#1f1a14` | `#f0e6d2` | `#d4956a` | 创意、人文 |

强制规则：
- 禁止使用`#FFFFFF`和`#000000`（印刷纸色美学，避免刺眼）
- 每页最多1个锚点色高亮元素（克制使用强调色）
- 色彩闭环：封面和封底必须使用相同锚点色

### 4.2 字体层级

| 层级 | 字号(SVG px) | 字重 | 用途 |
|------|-------------|------|------|
| H1 | 72-96 | 200 ExtraLight | 封面主标题 |
| H2 | 48-64 | 200 ExtraLight | 章节分隔页 |
| H3 | 36-48 | 300 Light | 内容页标题 |
| Body | 14-18 | 400 Regular | 要点、段落 |
| Meta | 10-12 | 500 Medium | 页码、引用 |

**铁律**：H1最小(72px) / Body最大(18px) ≥ **8:1**。违反即error。

### 4.3 网格与形状

- 16列CSS Grid布局，列间距16px
- 所有元素吸附网格，禁止自由坐标定位
- 仅直角：禁止`border-radius`、`box-shadow`、`linear-gradient`
- 纯色背景，不用图片背景或WebGL

### 4.4 呼吸节奏

相邻三页不能使用相同布局模板。模式必须交替：

```
封面(Hero) → 内容页 → 章节页(Hero) → 内容页 → 内容页(不同布局) → ...
```

评审Agent的`hierarchy`维度自动检查此项——连续三页同布局视为error。

### 4.5 七种布局模板

不要求LLM从零设计布局（效果不稳定），而是预先定义7种模板，LLM在每个模板内填充内容：

| 编号 | 名称 | 结构 | 适用 |
|------|------|------|------|
| L1 | 封面 | 标题居中 + 副标题 + 作者信息 | 首页 |
| L2 | 章节分隔 | 大号章节编号 + 标题（Hero页） | 章节过渡 |
| L3 | 要点列表 | 左侧标题 + 3-5个要点纵向排列 | 常规内容 |
| L4 | 图文双栏 | 左文右图 或 左图右文 | 解释说明 |
| L5 | 三列对比 | 三个等宽列 | 方法/方案对比 |
| L6 | 数据焦点 | 单一核心数字 + 解读文字 | 关键结论 |
| L7 | 封底 | Thank you / Q&A + 联系方式 | 末页 |

---

## 五、SVG → PPTX 编译管线

### 5.1 核心思路

借鉴 **PPT Master**（GitHub 1万+星）的做法：LLM不直接操作python-pptx（LLM学不会这个库的API），而是生成SVG代码——LLM天然就会写SVG。然后Python脚本做"方言翻译"：SVG和PowerPoint的DrawingML在结构上高度同构，可以近乎1:1映射。

### 5.2 元素映射表

| SVG元素 | python-pptx对象 | 映射属性 |
|---------|----------------|---------|
| `<rect>` | `MSO_SHAPE.RECTANGLE` | x, y, width, height, fill, stroke |
| `<circle>` | 椭圆/圆 | cx→left, cy→top, r→尺寸 |
| `<text>` | TextBox + Paragraph | x, y, font-size, font-family, fill |
| `<line>` | 线段 | x1, y1, x2, y2, stroke |
| `<path>` | 自由形状 | d→点序列 |
| `<linearGradient>` | GradientFill | 方向、色标 |

### 5.3 编译流程

```
SVG字符串
  → BeautifulSoup解析为DOM树
  → 遍历节点，按映射表创建python-pptx Shape对象
  → 单位转换：SVG px → EMU (× 9525)
  → 添加Shape到Slide → Presentation.save("output.pptx")
```

### 5.4 特殊处理

- **中文字体**：SVG的`font-family`映射到PPT安全字体（微软雅黑/等线/宋体）
- **图片**：`<image>`标签 → `slide.shapes.add_picture()`
- **容错**：BeautifulSoup宽松解析，跳过LLM偶发的畸形SVG节点并记录日志

---

## 六、前端（浏览器面板）

### 6.1 技术选型

单HTML文件 + 原生JavaScript WebSocket。不需要任何前端框架，不需要构建步骤。由FastAPI静态路由提供。

### 6.2 页面布局

```
┌──────────────────────────────────────────────────────┐
│  SlideWise                                  [状态栏]  │
├────────────────────────┬─────────────────────────────┤
│                        │                             │
│   对话面板 (左侧)       │     幻灯片预览网格 (右侧)     │
│                        │                             │
│  用户的消息             │   ┌──────┐ ┌──────┐        │
│  Agent的回复            │   │ 第1页 │ │ 第2页 │        │
│  大纲列表（可编辑）      │   │  ✓   │ │  ✓   │        │
│  评审问题卡片            │   └──────┘ └──────┘        │
│  修复结果               │   ┌──────┐ ┌──────┐        │
│                        │   │ 第3页 │ │ 生成中│        │
│                        │   │  ⚠   │ │  ... │        │
│  ┌──────────────────┐  │   └──────┘ └──────┘        │
│  │ 输入消息...  📎   │  │                             │
│  └──────────────────┘  │                             │
└────────────────────────┴─────────────────────────────┘
```

### 6.3 交互设计

- **对话驱动**：所有操作通过自然语言完成，没有结构化表单
- **文件上传**：拖拽PDF/Markdown到对话区，或点击📎选择文件
- **大纲编辑**：Agent返回大纲后渲染为可编辑列表，用户可直接修改标题、增减页
- **评审展示**：问题以可展开卡片呈现，每条有[修复]/[忽略]按钮
- **随时追加意见**：用户在任何阶段可以输入新要求（"第5页改用对比布局"）

### 6.4 幻灯片预览

- 生成阶段：缩略图逐页出现在网格中，带有入场动画
- 生成中：灰色骨架屏+旋转动画
- 有问题：⚠橙色脉冲标记
- 点击卡片：全尺寸灯箱预览，支持键盘左右翻页

### 6.5 五个阶段的状态切换

| 阶段 | 对话面板 | 预览网格 | 用户操作 |
|------|---------|---------|---------|
| 1.规划 | 展示大纲，等待确认 | 空 | 编辑大纲、添加页、确认 |
| 2.生成 | 显示生成进度 | 卡片逐个出现 | 纯观看 |
| 3.评审 | 展示问题卡片 | ⚠标记问题页 | 逐条决定修复/忽略 |
| 4.修复 | 展示修复进度 | 修改页重新渲染 | 验收、追加修复 |
| 5.完成 | 下载按钮 | 全部绿色✓ | 下载.pptx |

---

## 七、输入与输出

### 7.1 支持四种输入模式

| 模式 | 用户操作 | 处理方式 |
|------|---------|---------|
| 纯主题 | 打字："帮我做一个关于Transformer的PPT" | 直接送入生成Agent |
| PDF上传 | 拖入`attention_paper.pdf` | pdfplumber提取文本+章节结构 |
| Markdown上传 | 拖入`outline.md` | 保留标题层级作为大纲骨架 |
| 混合 | 拖入PDF + 打字"重点讲实验部分" | PDF内容 + 用户强调合并 |

### 7.2 自然语言意图提取

生成Agent自动从日常用语中提取参数，用户不需要学任何命令：

| 用户说 | 自动理解为 |
|--------|-----------|
| "用靛蓝色" / "科技风" / "深蓝色" | style=indigo |
| "8页左右" / "精简一点" / "别太多" | page_count≈8 |
| "瑞士风格" / "杂志感" / "极简风" | template=swiss |
| "水课用" / "随便搞一下" / "应付一下" | strict=false, 跳过评审 |
| "组会要用的" / "认真做" / "正式一点" | strict=true, 全流程评审 |

### 7.3 输出

- **主输出**：`.pptx`文件，所有元素是PowerPoint原生对象——可在PowerPoint/WPS/Keynote中自由编辑每个文本框、形状、颜色
- **中间产物**：SVG和PNG保存在临时目录，下载后自动清空

---

## 八、技术栈与依赖

| 组件 | 技术 | 说明 |
|------|------|------|
| Web服务器 | FastAPI + `websockets` | Python异步框架，原生WebSocket |
| LLM | DeepSeek V4 Flash | OpenAI兼容API，100万token上下文 |
| PDF解析 | pdfplumber | 提取文本+表格+章节 |
| SVG解析 | BeautifulSoup (lxml) | 容错HTML/XML解析 |
| PPTX生成 | python-pptx | 创建原生PowerPoint对象 |
| SVG→PNG | cairosvg | 生成缩略图供预览 |
| 前端 | 单HTML + 原生JS | 无框架，无构建，WebSocket直连 |
| 存储 | 无 | 内存会话，无需数据库 |

启动方式：`python main.py` → 浏览器自动打开 `http://localhost:8888`

---

## 九、实现计划与分工

### 9.1 开发周期

**DDL：6月10日晚23:59**（提交报告PDF+汇报PPT压缩包）

### 9.2 Person A — 后端 & Agent核心 

**核心职责**：Python后端、DeepSeek Agent集成、SVG→PPTX编译器

| 优先级 | 任务 | 预计耗时 |
|--------|------|---------|
| 🔴 P0 | 搭建FastAPI + WebSocket基础框架 | 2-3h |
| 🔴 P0 | 实现Agent·生成（System Prompt + JSON Schema + DeepSeek API调用） | 3-4h |
| 🔴 P0 | 实现SVG→PPTX编译器（映射表 + BeautifulSoup解析 + python-pptx组装） | 4-5h |
| 🔴 P0 | 实现PDF解析模块（pdfplumber提取文本+结构） | 1-2h |
| 🔴 P0 | 实现WebSocket协议（六种消息类型的收发） | 1-2h |
| 🟡 P1 | 实现Agent·评审（四个维度的检查规则） | 2-3h |
| 🟡 P1 | 实现会话管理（UUID + 内存dict + 自动清理） | 1h |
| 🟢 P2 | Markdown输入支持 | 0.5h |
| 🟢 P2 | 多语言（英文输出）支持 | 1h |

**总预计**：P0约12-16小时，P1约3-4小时，P2约1.5小时

### 9.3 Person B — 前端 & UX 

**核心职责**：浏览器界面、WebSocket通信、视觉体验

| 优先级 | 任务 | 预计耗时 |
|--------|------|---------|
| 🔴 P0 | 搭建HTML页面骨架（左侧对话面板 + 右侧预览网格 + 底部输入栏） | 3-4h |
| 🔴 P0 | 实现WebSocket客户端（六种消息类型的收发+状态管理） | 3-4h |
| 🔴 P0 | 实现对话面板（消息渲染、大纲展示与编辑、评审问题卡片） | 3-4h |
| 🔴 P0 | 实现文件拖拽上传（PDF/Markdown，进度显示） | 1-2h |
| 🔴 P0 | 实现幻灯片预览网格（卡片渲染、流式出现动画、⚠标记） | 2-3h |
| 🟡 P1 | 实现全尺寸灯箱预览（点击卡片、键盘翻页） | 1-2h |
| 🟡 P1 | CSS视觉打磨（Guizang风格的聊天面板、响应式布局、过渡动画） | 2-3h |
| 🟢 P2 | 流式生成动画优化（骨架屏、入场动效） | 1h |
| 🟢 P2 | 移动端响应式适配 | 1h |

**总预计**：P0约12-17小时，P1约3-5小时，P2约2小时

### 9.4 共同任务

| 任务 | 说明 |
|------|------|
| 🔴 联调集成 | WebSocket协议对齐、端到端流程测试、边界情况处理 |
| 🔴 报告撰写 | 英文ICLR模板，6个章节（见下方），2人分工撰写 |
| 🔴 汇报PPT | 展示SlideWise的运行效果、架构、创新点 |
| 🟡 对比实验 | 收集3-5个测试案例（论文PPT、水课PPT、大纲PPT），对比有无评审Agent的效果 |

### 9.5 关键接口约定（必须对齐）

**WebSocket消息协议**（两个人在此对接）：

服务端→客户端：
```json
{"type": "outline", "data": {"pages": [...]}}
{"type": "slide_generated", "data": {"index": 3, "svg": "...", "png_base64": "..."}}
{"type": "review_report", "data": {"issues": [...], "summary": "..."}}
{"type": "slide_fixed", "data": {"index": 3, "svg": "...", "png_base64": "..."}}
{"type": "done", "data": {"download_url": "/download/abc123"}}
{"type": "error", "data": {"message": "..."}}
```

客户端→服务端：
```json
{"type": "user_message", "data": {"text": "...", "files": ["base64..."]}}
{"type": "confirm_outline", "data": {"approved": true, "modified_outline": [...]}}
{"type": "fix_decisions", "data": {"fix": [3, 5], "ignore": [2], "feedback": "..."}}
{"type": "retry_slide", "data": {"index": 5, "feedback": "..."}}
{"type": "download", "data": {}}
```

---

## 十、报告撰写分工建议

报告使用英文，ICLR会议模板，6个标准章节：

| 章节 | 内容 | 建议负责人 |
|------|------|-----------|
| Abstract | 一句话概括：双Agent驱动的PPT自动生成 | 共同 |
| Introduction | CS学生做PPT的痛点、现有工具不足（Gamma/Beautiful.ai不可编辑） | B |
| Related Work | PPT Master、Guizang PPT、GenPilot、Paper PPT Agent | A |
| Method | 双Agent架构、风格约束系统、SVG→PPTX编译管线、聊天驱动交互 | A写架构+编译 / B写交互+前端 |
| Experiments | 定性对比（vs 无风格约束的LLM输出）、消融实验（有无评审Agent）、3个案例研究 | 共同 |
| Conclusion | 总结、局限（SVG艺术精度、评审不能看视觉效果）、未来工作 | B |

---

## 十一、创新点总结（用于报告和汇报）

1. **角色分离的双Agent质量循环**：同一模型（DeepSeek V4 Flash），不同System Prompt——生成Agent和评审Agent各司其职，形成"生成→审查→修复→再审查"的自动质量闭环。评审Agent检查12条具体规则，而非笼统的"好不好看"

2. **约束驱动的Guizang美学系统**：将Guizang PPT的瑞士国际主义风格量化为可验证的设计约束——4套调色板、5级字体层级（强制8:1比例）、16列网格、禁止圆角阴影渐变、呼吸节奏规则。所有规则由评审Agent自动验证

3. **聊天原生交互**：不做CLI、不做复杂表单。用户在浏览器里用自然语言驱动——"帮我把这篇论文转成组会PPT，靛蓝，8页"。对话面板+实时幻灯片预览，三个介入点全部在聊天中完成

4. **SVG→DrawingML编译**：借鉴PPT Master的"方言翻译"思路，LLM生成SVG（天然强项）→python-pptx编译为原生PowerPoint对象（textbox/shape/gradient全覆盖）→输出真正可编辑的.pptx。不是死图片，每个元素都能在PPT里修改

5. **零配置启动**：`python main.py` → 浏览器打开 → 开始对话。无数据库、无构建步骤、无CLI参数。DeepSeek API key通过环境变量配置

---

## 参考项目

| 项目 | GitHub | 借鉴了什么 |
|------|--------|-----------|
| PPT Master | [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) | SVG→python-pptx编译管线 |
| Guizang PPT Skill | [op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill) | 瑞士国际主义风格约束体系 |
| GenPilot | [27yw/GenPilot](https://github.com/27yw/GenPilot) | 多Agent协作的错误分析与修复 |
| Paper PPT Agent | [CRui5in/paper-ppt-agent](https://github.com/CRui5in/paper-ppt-agent) | 论文解析+Critic评审模式 |
| Presenton | [dbrainio/presenton](https://github.com/dbrainio/presenton) | 可编辑PPTX导出思路 |
