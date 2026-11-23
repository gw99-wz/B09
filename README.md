# B09 — 写作09｜方法与实验章节写作

玻尔分站赛「写作09｜方法与实验章节写作」参赛作品。

| 项 | 值 |
|-|-|
| 赛题 | 写作09｜方法与实验章节写作 |
| Challenge ID | `product-arena-05-64faa4a2` |
| 赛题页 | https://play.bohrium.com/challenge/product-arena-05-64faa4a2 |
| 提交物 | `submission/`（Skill 本体 + 确定性脚本 + 模板 + 文档 + 示例 + 回归题集） |
| 提交 | 已正式提交，人工评分排队（状态与分数以平台记录为准） |
| 自测 | **10/10 通过**（含 4 类反例） |
| 聚焦 | **写得准**（参数台账 + 数值防火墙）+ **做得着**（复现清单生成），贯通 **写得全** 与 **说得住** |

## 一句话

把散落的实验记录（配置 / 日志 / 代码 / 数据说明）变成一份**每个数字都能回到原始材料、每条步骤都带输入输出、缺口全部显式交给作者**的方法与实验章节。

模型只写"带槽位的散文"，数值由确定性渲染器从**参数台账**灌入；因此"为段落顺畅而补出的数值"在机制上写不进来。

## 四条守恒式

```
来源：canonical(ledger[p].value) == canonical(extract(material, locator))
渲染：rendered[slot]         == ledger[slot.param]
数字：Numbers(rendered)      == Numbers(substituted_slots) ∪ Whitelist
冲突：材料不一致时 ledger.status == "conflict"，绝不择一
```

第 3 条由 `submission/scripts/pk/firewall.py` 实现：渲染器记录每个槽位替换的字符区间，防火墙逐 token 判断归属；手写的、恰好等于台账值的数字同样会被拦截。

## 目录

```
B09/
├─ README.md
├─ .gitignore                 # 仅供 git 使用，不进提交包
├─ docs/PLAN.md               # 架构初稿
└─ submission/                # ← 打包根（playground submit --outputs）
   ├─ SKILL.md                # 入口
   ├─ GITHUB_URL.txt
   ├─ requirements.txt        # 仅标准库
   ├─ scripts/run.py          # init / check / all
   ├─ scripts/pk/             # 契约、材料、抽取、台账、渲染、防火墙、覆盖、复现、缺口、产物
   ├─ templates/              # 参数表 / 复现清单 / 追问清单 / 骨架
   ├─ docs/                   # METHOD / USAGE / LIMITS
   ├─ examples/mini/          # 合成示例（非正式案例）
   ├─ tests/run_tests.py      # 10 项回归
   └─ src/reproduce.py        # 一键复现示例
```

## 验证结果

| 项 | 结果 |
|-|-|
| 回归题集 | 10/10（未绑定数字、冲突、缺种子、套话限制、未知槽位、伪造提议、契约未知字段、幂等、打包） |
| 防火墙拦截 | 草稿写死 `32`（台账为 `64`）→ `E_UNBOUND_NUMBER`，exit 2，**不产出 `draft.md`**，只留 `draft.rejected.md` |
| 示例覆盖矩阵 | `coverage_score = 0.90`（27 present / 3 missing，缺硬件、单位、commit） |
| 示例复现清单 | `repro_score = 0.75`（6 present / 2 missing：commit、依赖文件） |
| 打包 | 47 个文本文件 / 158KB，无后缀名文件、无符号链接 |

## 硬约束

- 执行预算 **64 次模型请求 / 900 秒 / 单次 16384 tokens**；确定性脚本不消耗模型请求。
- 资源上限 **≤50 个 UTF-8 文本文件、单件 ≤500KB、合计 ≤2MB、无符号链接**；`submission/` 内一律带扩展名。
- `output_contract` 字段表不公开：运行时从 `/input/case.json` 解析，映射不到写 `null` 并进 `unresolved`。

详见 [`submission/docs/METHOD.md`](submission/docs/METHOD.md) 与 [`submission/SKILL.md`](submission/SKILL.md)。
