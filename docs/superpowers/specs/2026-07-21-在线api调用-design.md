# 在线 API 调用功能 - 设计文档

> 创建日期：2026-07-21
> 状态：待用户审阅
> 对应需求文档：[2026-07-21-在线api调用-requirement.md](../requirements/2026-07-21-在线api调用-requirement.md)
> 方案选择：方案 A（轻量改动）

---

## 一、架构概览

采用"轻量改动"方案：在 `mineru桥接.py` 新增几个与本地函数平行的在线 API 函数，`ner引擎.py` 根据当前模式选择调用本地还是在线的实现。**不引入抽象基类**，不做过度工程。

### 改造范围

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `主程序/mineru桥接.py` | 新增函数 | 加 3 个在线 API 相关函数 + 1 个地址规范化函数 |
| `主程序/ner引擎.py` | 改造方法 | 改 4 个方法（`_获取api地址`/`_检测lm可用性`/`_调用llm`/`_审核简称候选`）+ 新增 1 个辅助方法 |
| `主程序/app.py` | 改造 GUI + 方法 | 改造配置区 UI + 改 4 个状态相关方法 |
| `settings.json` | 扩展字段 | 加 4 个新字段 |
| `启动器.py` | **不改** | 依赖列表已含 `requests` |
| `文档解析器.py` / `脱敏处理器.py` / `格式保持器.py` / `_docx_xml工具.py` | **不改** | 与 LLM 后端无关 |
| `mineru桥接.py` 的 `MinerU引擎` 类 | **不改** | MinerU 是独立 CLI，与 LLM 后端无关 |
| NER 提示词 / 严格解析 / 兜底解析 | **不改** | 在线模型同样适用 |
| 依赖包 | **不新增** | `requests` 已支持 Authorization 头 |

---

## 二、配置数据结构

### 2.1 settings.json 扩展

```json
{
  "llm_mode": "local",
  "lm_port": 1234,
  "online_api_base": "",
  "online_api_key": "",
  "online_model": ""
}
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `llm_mode` | `"local"` \| `"online"` | `"local"` | 模式切换开关 |
| `lm_port` | int | `1234` | 本地模式用（现状，保留） |
| `online_api_base` | string | `""` | 在线模式用，如 `https://api.openai.com` |
| `online_api_key` | string | `""` | 在线模式用，如 `sk-xxx` |
| `online_model` | string | `""` | 在线模式用，如 `gpt-4o-mini` |

### 2.2 向后兼容

- 旧版 settings.json 没有新字段时，`读取用户设置()` 返回的 dict 用 `.get(key, 默认值)` 取值，默认 `llm_mode="local"`，其他字段为空字符串
- 现有 `读取用户设置()` 已做 `json.JSONDecodeError` 容错，无需额外改造

---

## 三、组件改造详情

### 3.1 mineru桥接.py

#### 新增函数 1：规范化在线api地址

```python
def 规范化在线api地址(原始地址: str) -> str:
    """智能规范化在线 API 地址，统一规范化到 /v1 这一级。

    规则（按顺序）：
    1. 去首尾空白；空字符串返回空字符串
    2. 不带协议头（http:// 或 https://）的，补 https://
    3. 去掉尾斜杠
    4. 用正则 r"^(https?://.*?/v1)" 非贪婪提取到第一个 /v1 为止：
       - 地址包含 /v1（如 /v1、/v1/、/v1/chat/completions、/compatible-mode/v1）
         -> 截取到 /v1 为止，去掉后面的路径段（处理用户填了完整地址的情况）
       - 地址不含 /v1 -> 补 /v1

    示例：
      http://119.6.186.168:40040                          -> http://119.6.186.168:40040/v1
      http://119.6.186.168:40040/v1                       -> http://119.6.186.168:40040/v1
      http://119.6.186.168:40040/v1/                      -> http://119.6.186.168:40040/v1
      http://119.6.186.168:40040/v1/chat/completions      -> http://119.6.186.168:40040/v1   （截断）
      https://api.openai.com                              -> https://api.openai.com/v1
      https://api.openai.com/v1                           -> https://api.openai.com/v1
      https://api.openai.com/v1/                          -> https://api.openai.com/v1
      https://api.openai.com/v1/chat/completions          -> https://api.openai.com/v1       （截断）
      api.openai.com                                      -> https://api.openai.com/v1
      https://dashscope.aliyuncs.com/compatible-mode      -> https://dashscope.aliyuncs.com/compatible-mode/v1
      https://dashscope.aliyuncs.com/compatible-mode/v1  -> https://dashscope.aliyuncs.com/compatible-mode/v1
    """
```

**智能识别的实现**：用正则 `r"^(https?://.*?/v1)"` 非贪婪匹配，提取到第一个 `/v1` 为止。
- 匹配到就截取（处理用户填了 `/v1/chat/completions` 完整地址的情况，去掉后面的 `/chat/completions`）
- 没匹配到就补 `/v1`
- 非贪婪 `.*?` 确保通义千问的 `/compatible-mode/v1` 也能正确匹配到 `/v1` 为止，不会过度截断

#### 新增函数 2：获取在线api模型列表

```python
def 获取在线api模型列表(api_base: str, api_key: str) -> list[dict]:
    """调用 GET {api_base}/models 获取模型列表。

    返回格式与 获取lm_studio模型列表() 对齐：
      [{"id": "gpt-4o-mini", ...}, {"id": "gpt-4o", ...}]

    异常：
      requests.HTTPError - 401（密钥错）/ 404（地址错）等
      requests.Timeout / ConnectionError - 网络问题
    """
    import requests
    规范化地址 = 规范化在线api地址(api_base)
    if not 规范化地址:
        raise ValueError("API 地址为空")
    if not api_key:
        raise ValueError("API 密钥为空")
    响应 = requests.get(
        f"{规范化地址}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=(180, 360),
    )
    响应.raise_for_status()
    return list(响应.json().get("data") or [])
```

#### 新增函数 3：探测在线api状态

```python
def 探测在线api状态(api_base: str, api_key: str, model: str = "") -> dict:
    """检测在线 API 连通性。

    返回格式与 探测lm_studio状态() 对齐：
      {"已启动": bool, "模型名称": str, "模型已加载": bool}

    逻辑：
      - 调 获取在线api模型列表() 拉取模型列表
      - "已启动"：能连通就 True
      - "模型已加载"：用户填了 model 且在列表里 -> True；
                     用户没填 model 但列表非空 -> True（取第一个）
                     用户填了 model 但不在列表里 -> False（可能 /models 接口不全，但也提示用户检查）
      - 异常时返回 {"已启动": False, "模型名称": "", "模型已加载": False}
    """
```

#### 保留不动的现有函数

- `读取lm_studio配置()`
- `读取用户设置()`（已返回整个 dict，无需改）
- `探测lm_studio地址()`
- `获取lm_studio模型列表()`
- `选择首选文本模型()`
- `探测lm_studio状态()`
- `MinerU引擎` 类

---

### 3.2 ner引擎.py

#### 3.2.1 新增辅助方法：读取当前 LLM 配置

```python
def _读取llm配置(self) -> dict:
    """从 settings.json 读取当前 LLM 模式和配置。

    返回：
      {
        "mode": "local" | "online",
        "api_base": str,   # 本地：探测lm_studio地址() 的结果；在线：规范化后的地址
        "api_key": str,    # 本地：空字符串；在线：sk-xxx
        "model": str,      # 本地：空（靠 _检测lm可用性 自动探测）；在线：用户填的模型名
      }
    """
    # 读 settings.json，根据 llm_mode 返回不同字段
```

#### 3.2.2 改造 _获取api地址

```python
def _获取api地址(self) -> str:
    配置 = self._读取llm配置()
    return f"{配置['api_base']}/chat/completions"
```

**说明**：本地模式 `配置['api_base']` 是 `http://127.0.0.1:1234/v1`，拼出 `http://127.0.0.1:1234/v1/chat/completions`（与现状一致）。在线模式 `配置['api_base']` 是规范化后的地址（已含 `/v1`），拼出 `https://api.openai.com/v1/chat/completions`。

#### 3.2.3 改造 _检测lm可用性

```python
def _检测lm可用性(self) -> bool:
    if self._可用 is True:
        return True
    配置 = self._读取llm配置()
    try:
        if 配置["mode"] == "online":
            # 在线模式
            if not 配置["api_base"] or not 配置["api_key"]:
                return False
            from .mineru桥接 import 探测在线api状态
            状态 = 探测在线api状态(配置["api_base"], 配置["api_key"], 配置["model"])
            if not 状态["已启动"]:
                return False
            # 模型名优先用用户填的，没填就取 /models 第一个
            self._MODEL = 配置["model"] or 状态["模型名称"]
            if not self._MODEL:
                return False
            self._可用 = True
            return True
        else:
            # 本地模式（沿用现有逻辑）
            from .mineru桥接 import 获取lm_studio模型列表, 选择首选文本模型
            模型列表 = 获取lm_studio模型列表()
            if 模型列表:
                首选模型 = 选择首选文本模型(模型列表)
                if 首选模型:
                    self._MODEL = 首选模型
                    self._可用 = True
                    return True
    except Exception:
        pass
    return False
```

#### 3.2.4 改造 _调用llm 和 _审核简称候选

在 `requests.post()` 调用里增加 `headers` 参数（仅在线模式带 Authorization）：

```python
配置 = self._读取llm配置()
请求头 = {}
if 配置["mode"] == "online" and 配置["api_key"]:
    请求头["Authorization"] = f"Bearer {配置['api_key']}"

resp = requests.post(
    self._获取api地址(),
    headers=请求头,  # 新增参数
    json={
        "model": self._MODEL,
        "messages": [...],
        "temperature": 0.0,
        "stream": False,
    },
    timeout=(180, 360),
)
```

**注意**：本地模式 `请求头` 是空 dict，`requests` 不会发送 Authorization 头，与现状一致（向后兼容）。

#### 3.2.5 模型名处理

| 模式 | `self._MODEL` 来源 |
|---|---|
| 本地模式 | `_检测lm可用性()` 自动探测（现状，调用 `选择首选文本模型`） |
| 在线模式 | 优先 `settings.json` 的 `online_model`；为空时 `探测在线api状态()` 返回的 `/models` 第一个 |

---

### 3.3 app.py GUI 改造

#### 3.3.1 配置区 UI 重构

把现在的 "LM Studio 配置" 区改成 "LLM 配置" 区。布局示意：

```
┌── LLM 配置 ──────────────────────────────────┐
│  [本地 LM Studio | 在线 API]  ← segmented    │
│                                                │
│  ─── 本地模式显示（lm_frame_local）───          │
│  端口: [1234] [测试连接]                        │
│  ● LM Studio: 已连接                           │
│                                                │
│  ─── 在线模式显示（lm_frame_online）───         │
│  API 地址: [https://api.openai.com    ]        │
│  API 密钥: [••••••••••••••••••••] ☐显示        │
│  模型名:   [gpt-4o-mini          ↓] [拉取列表] │
│            [测试连接]                          │
│  ● 在线 API: 已连接，可用模型数 12              │
└────────────────────────────────────────────────┘
```

**实现要点**：
- 用 `ctk.CTkSegmentedButton`（customtkinter 自带）做切换控件，值 `["本地 LM Studio", "在线 API"]`
- 两个子 frame：`lm_frame_local`（本地配置）和 `lm_frame_online`（在线配置）
- 切换时用 `grid_forget()` 隐藏一个、`grid()` 显示另一个
- 状态标签 `lm_status_label` 复用，文案根据模式切换（"LM Studio: xxx" 或 "在线 API: xxx"）

#### 3.3.2 在线配置区组件

| 组件 | 类型 | 说明 |
|---|---|---|
| API 地址输入框 | `CTkEntry` | 失焦时保存到 `settings["online_api_base"]` |
| API 密钥输入框 | `CTkEntry(show="*")` | 默认密码框；旁边加"显示"勾选框切换 `show=""` |
| 模型名下拉框 | `CTkOptionMenu` | 下拉选择；拉取失败时退化为可手填（动态切换为 `CTkEntry`） |
| 拉取列表按钮 | `CTkButton` | 点击调 `获取在线api模型列表()` 填充下拉框 |
| 测试连接按钮 | `CTkButton` | 点击根据模式调对应检测函数 |

#### 3.3.3 改造方法清单

| 方法 | 改造内容 |
|---|---|
| `build_ui` | 把 "LM Studio 配置" 区改造成 "LLM 配置" 区，加 segmented button + 两个子 frame |
| `_测试lm连接` | 重命名/新增分支：本地模式沿用现有端口验证；在线模式验证地址+密钥非空后调 `探测在线api状态()` |
| `_检测lm状态` | 根据 `llm_mode` 调 `探测lm_studio状态()` 或 `探测在线api状态()` |
| `_更新lm状态` | 文案根据模式切换："LM Studio: xxx" 或 "在线 API: xxx" |
| `_刷新lm状态` | 文案根据模式切换："检测中..." |
| 新增 `_切换llm模式` | segmented button 的回调：检查 `is_processing` -> 保存 `llm_mode` -> 切换子 frame -> 重新检测状态 |
| 新增 `_拉取模型列表` | 调 `获取在线api模型列表()` 填下拉框；失败则降级为可手填 |
| 新增 `_保存在线配置` | 失焦时保存 `online_api_base`/`online_api_key`/`online_model` 到 settings.json |
| 新增 `_切换密钥显示` | "显示"勾选框回调：切换密钥输入框的 `show` 属性 |

#### 3.3.4 切换时的处理

- 切换时如果 `is_processing=True`：拒绝切换，弹窗"处理中无法切换"
- 切换时立即保存 `llm_mode` 到 settings.json
- 切换时状态标签重置为"检测中..."
- 切换时异步调 `_检测lm状态()`（根据新模式）
- **注意**：`脱敏处理器` 每次 `__init__` 时新建 `NER引擎()` 实例，所以 `self._可用` 缓存在每次脱敏时自然重置，切换模式后不需要手动清

---

## 四、数据流

### 4.1 程序启动

```
读 settings.json
  -> 确定 llm_mode
  -> segmented button 选中对应段
  -> 显示对应子 frame（本地/在线）
  -> 填入已保存的配置（端口 / 地址+密钥+模型）
  -> 异步检测对应后端状态
  -> 状态灯显示绿/红 + 文案
```

### 4.2 用户切换模式

```
点 segmented button
  -> 检查 is_processing
       True  -> 弹窗"处理中无法切换"，segmented button 回滚到原选中段
       False -> 继续
  -> 保存 llm_mode 到 settings.json
  -> grid_forget() 当前子 frame，grid() 另一个子 frame
  -> 状态标签重置为"检测中..."
  -> 异步调 _检测lm状态()
  -> 状态灯更新
```

### 4.3 用户填配置（失焦保存）

```
输入框失焦
  -> 保存到 settings.json 对应字段
  -> 不立即检测（避免每次输入都触发检测）
  -> 下次点测试连接或开始脱敏时才用新配置
```

### 4.4 点测试连接

```
根据 llm_mode
  -> 本地模式（现状）：
       验证端口号 -> 保存 lm_port -> 探测lm_studio状态() -> 显示结果
  -> 在线模式：
       验证 api_base 非空 -> 验证 api_key 非空
            空 -> 提示"请先填写 API 地址和密钥"，不发请求
       调 探测在线api状态(api_base, api_key, model)
       成功 -> 显示"● 在线 API: 已连接，可用模型数 N" + 给一次费用提示弹窗
       失败 -> 根据异常类型显示：
                401 -> "API 密钥无效，请检查"
                404 -> "API 地址无效或模型不存在"
                Timeout/ConnectionError -> "连接失败，请检查网络或 API 地址"
```

### 4.5 点拉取模型列表

```
检查 api_base / api_key 是否为空
  -> 空 -> 提示"请先填写 API 地址和密钥"，不拉取
调 获取在线api模型列表(api_base, api_key)
  -> 成功 -> 填到下拉框，自动选中匹配 online_model 的项（或第一个）
  -> 失败 -> 提示"拉取失败：{错误}"，下拉框切换为可手填的 CTkEntry
```

### 4.6 开始脱敏（在线模式）

```
脱敏处理器.__init__ -> NER引擎()
  -> NER引擎.文本脱敏 -> 识别实体 -> _检测lm可用性()
       -> 在线模式：探测在线api状态() 验证连通性
       -> 不可用 -> NER 跳过，纯正则模式（现有降级逻辑）
       -> 可用 -> _调用llm() 带 Authorization 头调在线 API
  -> 其余流程不变（正则、脱敏、AC自动机、日期、金额）
```

---

## 五、错误处理

| 错误场景 | 检测点 | 处理方式 |
|---|---|---|
| API 地址为空时点测试连接/拉取列表 | app.py | 提示"请先填写 API 地址"，不发请求 |
| API 密钥为空时点测试连接/拉取列表 | app.py | 提示"请先填写 API 密钥"，不发请求 |
| API 密钥错误（HTTP 401） | `requests.HTTPError` | 提示"API 密钥无效，请检查" |
| API 地址错误（HTTP 404） | `requests.HTTPError` | 提示"API 地址无效或模型不存在" |
| 模型名错误（HTTP 404） | `requests.HTTPError` | 提示"模型不存在，请检查模型名或点'拉取模型列表'" |
| 网络不通/超时 | `requests.Timeout` / `ConnectionError` | 沿用现有重试机制（2 次，间隔 3s/6s），失败后降级为纯正则模式 |
| base_url 格式错误 | `规范化在线api地址()` 返回空 | 提示"API 地址格式无效" |
| 拉取模型列表失败 | `获取在线api模型列表()` 异常 | 提示"拉取失败：{错误}"，下拉框退化为可手填 |
| 处理中点切换模式 | app.py | 禁用切换控件，弹窗"处理中无法切换" |

**复用现有重试机制**：`_调用llm()` 已有 2 次重试逻辑（间隔 3s/6s），对 5xx 服务端错误和传输错误重试，4xx 不重试。在线模式直接复用，不额外改造。

---

## 六、测试策略

### 6.1 单元测试（新增到 `开发测试/`）

| 测试文件 | 测试内容 |
|---|---|
| `test_规范化在线api地址.py` | 覆盖各种输入：带/不带协议头、带/不带 `/v1`、带/不带尾斜杠、空字符串、通义千问的 `/compatible-mode` 路径 |
| `test_读取llm配置.py` | 本地模式返回本地地址；在线模式返回规范化地址+密钥+模型；旧版 settings.json（无新字段）默认本地模式 |
| `test_获取在线api模型列表.py` | mock `requests.get`，验证请求头含 `Authorization: Bearer {key}`、URL 拼接正确、返回格式转换正确 |
| `test_探测在线api状态.py` | mock，验证：空模型列表、模型在列表里、模型不在列表里、网络异常 |

### 6.2 集成测试（改造现有测试或新增）

| 测试 | 测试内容 |
|---|---|
| `test_ner引擎_在线模式请求头` | mock `requests.post`，验证在线模式请求头含 Authorization、本地模式不含 |
| `test_ner引擎_本地模式回归` | 现有测试全部通过（向后兼容） |

### 6.3 手动测试

1. 用 DeepSeek 真实 API（`https://api.deepseek.com` + `deepseek-chat`）跑一次脱敏流程
2. 用 OpenAI 官方 API 跑一次脱敏流程
3. 切换本地/在线模式各跑一次，验证状态灯正确、配置持久化

### 6.4 回归测试

运行 `开发测试/` 目录下所有现有测试，确保本地模式不受影响。

---

## 七、不做的事（YAGNI）

- 不内置常见 API 提供商预设（用户选了自定义地址）
- 不改 MinerU 引擎（MinerU 是独立 CLI，与 LLM 后端无关）
- 不做多后端并发（同一时间只用一个）
- 不改 NER 提示词和解析逻辑（在线模型同样适用）
- 不做 API Key 加密存储（用户接受明文）
- 不做用量统计/费用监控（只在测试连接成功后给一次提示弹窗）
- 不引入抽象基类（方案 A，不做过度工程）
- 不做流式响应（stream=False 现状，在线 API 也用非流式）

---

## 八、风险与缓解

| 风险 | 缓解措施 |
|---|---|
| API Key 明文存储，文件被偷就泄露 | 在 readme 和界面提示"请勿分享 settings.json"；密钥输入框默认密码框 |
| 用户误填错地址导致脱敏失败 | `规范化在线api地址()` 智能补全；测试连接按钮给清晰反馈 |
| 在线 API 比本地慢，大文档超时 | 沿用现有 360s 读取超时 + 2 次重试；超时后降级纯正则 |
| 不同在线 API 的 `/v1/models` 响应格式可能略有差异 | `获取在线api模型列表()` 容错处理：`data` 字段缺失时返回空列表 |
| 切换模式时正在脱敏导致状态错乱 | `is_processing` 检查，处理中禁用切换 |

---

## 九、待用户审阅的要点

请重点审阅以下几点，确认后进入阶段 3（实施计划）：

1. **配置数据结构**：`llm_mode` + 3 个 online_* 字段，是否够用？
2. **地址智能规范化规则**：用正则 `r"/v1(/.*)?$"` 识别已含 `/v1` 的情况，是否合理？
3. **GUI 布局**：segmented button + 两个子 frame 切换，是否符合预期？
4. **模型名下拉框降级**：拉取失败时切换为可手填 CTkEntry，是否接受？
5. **状态文案**：本地模式 "LM Studio: xxx"，在线模式 "在线 API: xxx"，是否清晰？
6. **测试范围**：4 个新单元测试 + 1 个集成测试 + 手动测试，是否充分？
