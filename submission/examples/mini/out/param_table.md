# 参数表（Parameter Ledger）

> 每个取值都绑定到材料 locator；`conflict` 表示材料互相矛盾，正文不得择一。

| 参数 | 取值 | 单位 | 作用对象 | 状态 | 来源 |
|-|-|-|-|-|-|
| `batch_size` | 64 | — | all | verified | materials/run_train.sh:3 |
| `checkpoint` | best.pt | — | all | verified | materials/run_train.sh:4 |
| `config` | config.yaml | — | all | verified | materials/run_train.sh:3 |
| `cuda_version` | 12.1 | — | all | verified | materials/train.log:4 |
| `cuda_visible_devices` | 0 | — | all | verified | materials/run_train.sh:2 |
| `device` | cuda | — | all | verified | materials/train.log:2 |
| `epochs` | 30 | — | all | verified | materials/train.log:6 |
| `model_name` | ResNet-50 | — | all | verified | materials/config.yaml:9 |
| `model_pretrained` | true | — | all | verified | materials/config.yaml:10 |
| `python` | 3.11.9 | — | all | verified | materials/train.log:3 |
| `seed` | 42 | — | all | verified | materials/run_train.sh:3 |
| `split` | test | — | all | verified | materials/run_train.sh:4 |
| `split_seed` | 42 | — | all | verified | materials/dataset.md:5 |
| `test_batch_size` | 128 | — | test | verified | materials/train.log:9 |
| `train_batch_size` | 64 | — | train | verified | materials/config.yaml:2 |
| `train_learning_rate` | 0.001 | — | train | verified | materials/config.yaml:3 |
| `train_max_epochs` | 30 | — | train | verified | materials/config.yaml:5 |
| `train_num_workers` | 4 | — | train | verified | materials/config.yaml:7 |
| `train_seed` | 42 | — | train | verified | materials/config.yaml:6 |
| `train_weight_decay` | 0.0001 | — | train | verified | materials/config.yaml:4 |
| `val_batch_size` | 128 | — | validation | verified | materials/train.log:8 |

共 **21** 个参数；verified 21 / conflict 0。
