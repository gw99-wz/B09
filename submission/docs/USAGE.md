# USAGE — 完整调用步骤

## 0. 环境

- Python ≥ 3.11（仅标准库；`tomllib` 随 3.11 提供）。
- 无需 `pip install`；`requirements.txt` 为空声明。
- 所有脚本以 UTF-8 读写，输出统一 LF。

## 1. 目录

```
submission/
├─ SKILL.md
├─ scripts/run.py          # CLI
├─ scripts/pk/             # 确定性引擎
├─ templates/              # 参数表 / 复现清单 / 追问清单 / 骨架
├─ docs/                   # METHOD / USAGE / LIMITS
├─ examples/mini/          # 合成示例（非真实案例）
├─ src/reproduce.py        # 一键复现示例
└─ tests/run_tests.py      # 回归题集
```

## 2. 三步调用

```bash
# 1) 解析 case 与材料，生成台账与骨架
python scripts/run.py init --case /input/case.json --work /app/work

# 2) 编辑 /app/work/draft.src.md（数字写成槽位）

# 3) 渲染 + 防火墙 + 复现清单 + 契约适配
python scripts/run.py check --case /input/case.json --work /app/work --out /app/output
```

`all` 等于 init + check。

可选：

```bash
--proposals /app/work/param_proposals.json   # 模型提议参数（需 locator + quote）
--allow /app/work/allowlist.txt              # 允许出现的字面量数字（每行一个，可带 # 注释）
--draft /app/work/custom.draft.md            # 自定义草稿路径
```

## 3. 槽位写法

```markdown
批大小 {{P:train_batch_size}}，学习率 {{P:train_learning_rate}}，
数据集 {{D:D1}}，基线 {{C:C1}}。
```

- `P:` 后可以写参数名（`train_batch_size`）或台账 id（`P_train_batch_size`）。
- `.raw` / `.unit` / `.name` 取字段。
- `{{?commit}}` 表示作者待确认，渲染为 `[待确认:commit]` 并进入追问。

## 4. 检查输出

```bash
python - <<'PY'
import json
a = json.load(open('/app/output/audit.json'))
print(a['status'], len(a['unbound_numbers']), len(a['render_errors']))
PY
```

- `status`：`ok / partial / failed`
- `unbound_numbers`：未绑定数字明细（token、行、列、上下文）
- `render_errors`：未知/冲突槽位
- `limitation_issues`：限制条件问题

## 5. 异常处理

| 现象 | 处置 |
|-|-|
| `E_UNBOUND_NUMBER` | 把字面量换成 `{{P:...}}`；确实需要保留的常数写入 `allowlist.txt` 并注明原因 |
| `E_UNKNOWN_SLOT` | 查 `ledger.json` 的 `id` / `name` |
| `E_CONFLICT_SLOT` | 不要改数字；在正文写 `{{?key}}`，等作者确认 |
| `E_VAGUE_LIMIT` | 把套话改成"当…时…失效；适用范围…" |
| 材料是扫描 PDF | 先用 OCR 转文本；OCR 文本作为新材料参与同样的 locator 校验 |
| 没有 `output_contract` | 引擎自动降级为 `unresolved`，`result.json` 仍包含 `case_id` 与全部已知产物 |

## 6. 自测

```bash
python tests/run_tests.py        # 10 项回归，含 4 类反例
python src/reproduce.py          # 运行 examples/mini 并生成 execution/run.log
```

反例题集覆盖：未绑定数字、参数冲突、缺种子、套话限制、未知槽位、伪造提议、契约未知字段、幂等性、打包合规。

## 7. 最小示例

`examples/mini/` 为**合成示例**（非真实案例），输出见 `examples/mini/out/`。

```bash
python src/reproduce.py
```

预期（示例，非正式评测）：

- `status: partial`（缺 commit）
- `coverage_score > 0.9`
- `repro_score = 0.75`
- `unbound_numbers: 0`

## 8. 打包合规自检

`check` 结束会写 `pack_report.json`，并在 `docs/LIMITS.md` 列出规则：
≤50 个文本文件、单件 ≤500KB、合计 ≤2MB、无符号链接、`submission/` 内无无后缀名文件。
