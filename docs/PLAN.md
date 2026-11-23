# B09 技术架构（初稿）

> 目标：在 64 次模型请求 / 900 秒预算内，把散落的实验材料整理成一份
> **数字守恒、步骤可执行、复现可照做、缺口可追问**的方法与实验章节。
> 核心思想：**模型负责"把话说顺"，脚本负责"把数看住"。**

---

## 0. 一句话架构

```
材料 ──► 候选抽取(确定性) ──► 台账(唯一事实源) ──► 草稿槽位(模型) ──► 渲染 ──► 数值防火墙 ──► 成稿
              │                    │                    │                              │
              └── locator ─────────┴── 冲突/缺口 ───────┴── 未绑定数 ─────────────────► 追问/复审
```

模型不直接产出数字，只产出**引用台账 id 的槽位**；数值由渲染器灌入。
因此"散文里的每个数"在结构上只能来自材料，无法被模型顺手编出来。

---

## 1. 契约层（Contract-first）

- 运行时读 `/input/case.json`，解析 `output_contract` 字段表（构建期不硬编码）。
- 建 `ContractMap`：声明字段 → 产物生产者（draft / ledger / repro / gaps …）。
- 映射不到 → 写 `null`，登记 `unresolved[]`，绝不猜测。
- 交付 `result.json`：`case_id` + 原字段 + `status` + `sources` + `uncertainty` + `change_records`。

## 2. 材料层（Material Layer）

- 全量登记输入：`md / txt / yaml / yml / json / toml / ini / cfg / log / csv / py / sh / tex`。
- 建 `MaterialIndex`：`file → 行号 + 字节偏移 + 原始引文 + 规范化引文 sha256`。
- PDF：`pdf-text-tool` 抽文本并保留页锚点；扫描件回退 OCR，并标注 `ocr=true`。
- 二进制/不可读文件跳过并记录，不静默忽略。

## 3. 六类要素的确定性抽取（写得全）

| 要素 | 抽取来源 | 必填子字段 |
|-|-|-|
| 步骤 | 协议文档、脚本、shell 记录 | 输入 / 操作 / 输出 / 判断条件 |
| 实验设置 | 日志、环境文件、README | 硬件 / 软件版本 / 运行环境 / 种子 / 重复次数 / 训练-验证-测试分离 |
| 参数 | 配置文件、argparse 默认值、代码字面量、`key=value` 日志 | 名称 / 取值 / 单位 / 作用对象 / 来源 locator |
| 数据集 | 数据说明、配置、日志 | 名称 / 版本 / 规模 / 预处理 / 划分比例 / 随机方式 / 各子集用途 |
| 对照 | 实验记录、结果表 | 基线及版本 / 是否同预算 / 指标 / 统计方式 |
| 复现与限制 | 全部材料 | 代码版本 / 环境 / 命令 / 数据获取 / 失效场景 |

每个抽取器输出 `Candidate{key, value, unit, scope, locator, confidence}`，**只做候选**，不做裁决。

## 4. 参数台账（唯一事实源）

`ledger.json` 的核心结构：

```json
{
  "params": [{
    "id": "P_lr",
    "name": "learning_rate",
    "value": "0.001",
    "unit": "1",
    "scope": "train",
    "source": {"file": "config.yaml", "locator": "L7", "quote": "lr: 0.001", "sha256": "..."},
    "status": "verified | conflict | unverified",
    "alternatives": []
  }]
}
```

### 4.1 对齐校验（"准"的第一道闸）

对每条候选，脚本**回读材料 locator**，规范化（去引号、统一单位、解析数值）后与候选比对：

- 一致 → `verified`
- 不一致 → `E_LEDGER_MISMATCH`，保留双方，进复审
- 材料互相冲突 → `status=conflict`，两个 locator 都留，`alternatives[]` 全列，交作者确认

**禁止**：脚本或模型在冲突时"挑一个看起来对的"。

### 4.2 模型只能"提名"，不能"定值"

模型若参与参数抽取，必须输出严格 JSON：`{key, value, locator, quote}`。
脚本校验 `quote` 是否真能在 locator 处找到、`value` 是否与 `quote` 规范化后相等。
不通过 → 拒绝，不进入台账。这是"防瞎编"的第一层。

## 5. 草稿槽位协议（模型写作的唯一接口）

模型写 `draft.src.md`，其中**任何实测数值都必须写成槽位**：

| 槽位 | 渲染结果 |
|-|-|
| `{{P:param_id}}` | 台账里的 `value` + `unit` |
| `{{D:dataset_id}}` | 数据集描述（名称/版本/规模/划分） |
| `{{C:control_id}}` | 基线描述（名称/版本/同预算标记） |
| `{{?key}}` | 显式 TODO，渲染为 `[待确认:key]`，并进追问清单 |

正文结构由骨架强制：`Methods`（步骤）→ `Experimental Setup`（设置/参数/数据/对照）→ `Reproducibility`（清单）→ `Limitations`（场景化限制）。
模型不能新增章节、不能把两类条件写串。

## 6. 渲染 + 数值防火墙（"准"的第二道闸，核心创新）

### 6.1 渲染

渲染器把槽位替换为台账值，同时记录 `substitution_map`：
`slot → value → param_id → source.locator`。

### 6.2 数值防火墙

对渲染后的成稿做 token 级扫描，抽出所有数字字面量（含科学计数、百分比、区间、单位）：

1. **bound**：等于某次替换值 → 通过
2. **whitelisted**：年份、章节/公式/图表编号、允许的常数 → 通过
3. **unbound**：其余 → `E_UNBOUND_NUMBER`，**硬失败**，成稿退回

### 6.3 守恒式（"不变量守恒"的变体）

> `Numbers(rendered) ≡ Numbers(substituted_slots) ∪ Whitelist`

且对每个槽位：

> `value(slot) ≡ canonicalize(ledger[param_id].value) ≡ canonicalize(extract(material, locator))`

两道等式由脚本在构建时校验，任一不成立即失败。
**数值不能在散文里被创造或消灭，只能在 材料 → 台账 → 槽位 → 渲染 的管道里流动。**
这就是把"参数与配置/日志/代码一致"从"要求"变成"编译期约束"。

### 6.4 交叉一致性

- 正文数值 vs 参数表 vs 摘要：同一 `param_id` 必须同值（单一来源）。
- 单位规范化后再比较（`1e-3` / `0.001` / `10^-3` 视为同一值）。
- 参数表里出现的每个 `param_id` 必须在正文至少被引用一次，反之亦然（孤儿检测）。

## 7. 复现清单生成（做得着）

由台账 + 材料**确定性生成** `repro_checklist.md`，每项带 `status ∈ {present, missing, inferred}` 与 locator：

| 项 | 来源 |
|-|-|
| 代码版本 | `.git` / `VERSION` / 日志里的 commit |
| 环境 | 环境文件 / 日志头 / requirements 哈希 |
| 数据获取 | 数据说明 / 配置 / 脚本 |
| 种子与重复 | 台账 |
| 运行命令 | 日志、脚本、shell 记录 |
| 预期产物 | 结果表 / 输出目录清单 |

- `missing` 项打印为 `[MISSING]` + 需要作者补什么，**不允许省略**。
- 命令若不在材料中出现，标 `constructed` 并说明推导依据。
- 输出 `repro_score = present / required`，作为"做得着"的可复核指标。

## 8. 缺口与限制（说得住）

### 8.1 缺口登记

`gaps.json` 每条：`{element, what, why(材料证据), impact, question_to_author, status}`。

### 8.2 限制条件四元组

每条限制必须写全：**具体失效场景 / 失效机制 / 适用范围 / 支撑证据**。
套话词表（"受限于时间""未来工作""广泛适用"等）命中即 `E_VAGUE_LIMIT`。

### 8.3 闭环

每个缺口必须落到：草稿里的 `{{?key}}` 标记 **或** `author_queries.md` 的一条追问。
不允许"材料没有就不写"。

## 9. 异常处理

| 情况 | 处置 |
|-|-|
| 无配置文件 | 参数全标 `unverified`，正文用 `{{?}}`，进追问 |
| 参数冲突 | `conflict` + 双 locator，绝不择一 |
| 数据集版本不明 | 缺口 + 追问，正文不写版本号 |
| `output_contract` 缺失/未知 | 通用 schema + `unresolved` |
| 材料是扫描 PDF | OCR + `ocr=true` 标注，低置信度入复审 |
| 只能交付部分 | `status=partial` + `limits[]` |

## 10. 产物清单

- `draft.md` / `draft.tex`（条件允许时 `draft.pdf` + `draft.page1.png` 预览）
- `result.json`（契约字段 + case_id + 状态 + 来源 + 不确定 + 修改记录）
- `ledger.json`、`substitution_map.json`、`audit.json`
- `repro_checklist.md`、`gaps.json`、`author_queries.md`
- `evidence_map.json`（段落/句子 → locator）

## 11. 为什么这样能赢

- **确定性部分**（抽取、对齐、渲染、防火墙、清单）不消耗模型请求，稳且可复跑。
- **可复核的硬结构**（台账、守恒式、清单、缺口）恰好是人工评分"结果可核验性 / 创新证据"最认的东西。
- 与"填空式模板"的本质区别：模板只保证**格式全**；本方案保证**每个数有出处、每个缺口有去向**。
