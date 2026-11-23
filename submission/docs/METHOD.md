# METHOD — 判定规则与阈值

本文件说明 `scripts/pk/` 里每条机制的确切规则，便于第三方复核与二次开发。

## 1. 守恒式（写得准）

记：

- `M` = 材料集合（每个文件带 `file:line` locator 与原文引文）
- `L` = 参数台账（每个参数一条记录，含 canonical value 与 locator）
- `S` = 草稿中的槽位集合
- `R` = 渲染后的正文
- `W` = 白名单（小节编号、列表编号、图表/公式引用、`--allow` 文件）

三条等式在 `check` 时逐条校验：

1. **来源等式**：`∀p ∈ L, canonical(L[p].value) == canonical(extract(M, L[p].locator))`
   —— 台账值必须等于材料在 locator 处的值；不成立即 `E_LEDGER_MISMATCH` 或 `conflict`。
2. **渲染等式**：`∀s ∈ S, R[s] == L[s.param]` —— 渲染值只来自台账。
3. **数字守恒**：`Numbers(R) == Numbers(S) ∪ W`
   —— 正文中任何数字必须落在某个槽位替换的字符区间内，或属于白名单。

第 3 条由 `pk/firewall.py` 实现：渲染器记录每个替换的 `(start, end)` 区间，防火墙对每个数字 token 做区间归属判断。**手写的、恰好等于某个台账值的数字也会被拦截**，因为它不在任何替换区间内。

## 2. 数值分类

| 类别 | 判定 | 处理 |
|-|-|-|
| bound | token 位置落在某次槽位替换的区间内 | 通过 |
| whitelisted | 小节编号 `^#{1,6}\s+[\d.]+`、列表编号 `^\s*\d+[.)]`、`Table/Figure/Eq./Section N`、`--allow` 中的值 | 通过 |
| unbound | 其余 | `E_UNBOUND_NUMBER`，硬失败 |

## 3. 参数抽取与冲突

- 抽取器：YAML 子集、JSON、TOML、INI、日志 `key=value`、shell 参数、argparse 默认值、Python 常量、文档粗体/`key: value`。
- 键路径保留层级：`train.batch_size` → `train_batch_size`，避免训练/验证同名参数被错误合并。
- 别名只做**叶子级**替换：`lr → learning_rate`、`bs → batch_size`、`wd → weight_decay`。
- 同一键、同一 canonical 值 → `verified`（保留全部来源）。
- 同一键、不同 canonical 值 → `conflict`（保留全部 alternatives，**不择一**）。
- 候选必须通过 locator 回读校验（引文出现在该行）才进入台账。

## 4. 覆盖矩阵（写得全）

六类 × 必填子字段，`present / partial / missing`：

| 类 | 子字段 | 判定来源 |
|-|-|-|
| steps | input / operation / output / decision | 正文编号步骤数 > 0 |
| settings | hardware / software / environment / seed / repeats / split | 版本线索、`seed` 参数、对照 `stat`、数据集 `split` |
| params | name / value / unit / scope / source | 台账记录完整性 |
| datasets | name / version / size / preprocess / split / random | 数据集结构化字段 |
| controls | baseline / version / budget / metric / stat | 对照结构化字段 |
| repro | code_version / environment / command / data_access | 复现清单条目状态 |

`coverage_score = (present + 0.5×partial) / total`。

## 5. 复现清单（做得着）

八项：代码版本、运行环境、依赖安装、数据获取、随机种子、重复次数、运行命令、预期产物。

- `present`：有材料直接支撑；
- `partial`：只有部分信息（如数据集有名称无版本、重复次数推断）；
- `missing`：材料中不存在，必须打印 `[MISSING]` 并进入追问。

`repro_score = (present + 0.5×partial) / total`。

## 6. 限制条件（说得住）

- 必须存在 `Limitations / 限制` 小节，否则 `E_MISSING_LIMITS`。
- 套话词表命中即 `E_VAGUE_LIMIT`（如"受限于时间""未来工作""广泛适用"）。
- 每条限制需含具体场景触发词（当/如果/一旦/在…情况下/if/when/fails）否则 `E_NO_SCENARIO`；少于 18 字符记 `E_SHALLOW_LIMIT`。

## 7. 契约适配

`output_contract` 支持 list / dict（fields|required|properties|outputs|items|schema）/ string 三种形态。
字段按名称启发式映射到产物；映射不到写 `null` 并登记 `unresolved_contract_fields`。
**构建期不硬编码任何字段名。**

## 8. 退出码

| 码 | 含义 |
|-|-|
| 0 | 通过（可能 `partial`：缺口已记录） |
| 2 | 硬失败（未绑定数字 / 未知槽位 / 冲突槽位 / 限制缺失或套话） |
| 1 | 用法或 IO 错误 |
