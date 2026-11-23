# Submission — Method & Experiment Provenance Kit

本目录是打包根（对应 `playground submit --outputs submission`）。
入口：`SKILL.md`；一键复现：`src/reproduce.py`；回归：`tests/run_tests.py`。

## 组成

| 路径 | 作用 |
|-|-|
| `SKILL.md` | 入口与调用协议 |
| `scripts/run.py` | CLI：`init / check / all` |
| `scripts/pk/` | 契约、材料、抽取、台账、渲染、防火墙、覆盖、复现、缺口、产物 |
| `templates/` | 参数表 / 复现清单 / 追问清单 / 骨架 |
| `docs/` | METHOD / USAGE / LIMITS |
| `examples/mini/` | 合成最小示例（材料 + 槽位草稿 + 生成的 out） |
| `tests/run_tests.py` | 10 项回归（含 4 类反例） |
| `src/reproduce.py` | 重建示例并写 `execution/run.log` |

## 合规

- 纯文本、全部带扩展名；无符号链接。
- `examples/mini/out/` 为**示意输出**，不是正式案例结果。
- 平台正式案例由评测系统提供，本包不内置任何正式答案。
