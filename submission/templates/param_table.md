# 参数表模板

> 每一行都必须能回到材料 locator；冲突行写两个来源，不做取舍。

| 参数 | 取值 | 单位 | 作用对象 | 状态 | 来源 |
|-|-|-|-|-|-|
| `learning_rate` | 0.001 | 1 | train | verified | `config.yaml:3` |
| `batch_size` | 64 | samples | train | verified | `config.yaml:2` |
| `seed` | 42 | 1 | all | verified | `train.log:5` |
| `lr`（冲突示例） | 0.1 或 0.01 | 1 | train | conflict | `config.yaml:1` / `train.log:2` |
