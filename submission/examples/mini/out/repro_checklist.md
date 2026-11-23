# 复现清单（Reproduction Checklist）

> 由参数台账与材料确定性生成；`[MISSING]` 表示材料不足，需作者确认，不是笔误。

| 项 | 内容 | 状态 | 来源 |
|-|-|-|-|
| 代码版本 | [MISSING] commit / release | missing | — |
| 运行环境 | Python 3.11.9; CUDA 12.1 | present | log |
| 依赖安装 | [MISSING] requirements.txt | inferred | — |
| 数据获取 | CIFAR-10 v1.0; train 50000 / val 5000 / test 5000 | present | dataset note |
| 随机种子 | seed = 42 | present | materials/run_train.sh |
| 重复次数 | 3 repeats | present | control note |
| 运行命令 | python train.py --config config.yaml --seed 42 --batch_size 64 | present | materials/run_train.sh |
| 预期产物 | best.pt | present | materials/run_train.sh |

**覆盖率（present + 0.5×partial）/ total = 0.75**（present 6 / partial 0 / missing 2 / total 8）

## 需作者补充

- `code_version`：请作者提供代码仓库 commit 或 release 版本号
