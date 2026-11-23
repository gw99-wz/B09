# Methods

## 1. Materials and Data

All experiments use CIFAR-10 v1.0. The training, validation and test subsets follow the split declared in the dataset note, and preprocessing follows the same note (random crop and horizontal flip). The split seed is 42.

## 2. Method Steps

1. **输入**：读取 CIFAR-10 v1.0 的原始数据，按数据集说明完成预处理与划分。
2. **操作**：调用 `run_train.sh`，以 config.yaml 为配置启动训练，批大小 64，初始学习率 0.001。
3. **输出**：每个 epoch 写出验证集准确率与检查点 best.pt。
4. **判断条件**：训练到 30 个 epoch 后停止；若验证集指标不再提升则提前终止。

## 3. Experimental Setup

### 3.1 Hardware and Software

训练在单卡 GPU 上完成，Python 版本 3.11.9，CUDA 版本 12.1，可见设备编号 0。

```
python train.py --config config.yaml --seed 42 --batch_size 64
```

### 3.2 Training, Validation and Test Protocol

训练使用 64 的批大小与 4 个数据加载进程；验证与测试分别使用 128 与 128 的批大小，二者与训练设置分开记录。随机种子为 42。

### 3.3 Parameters

| 参数 | 取值 | 单位 | 作用对象 |
|-|-|-|-|
| `train_batch_size` | 64 | - | train |
| `train_learning_rate` | 0.001 | - | train |
| `train_weight_decay` | 0.0001 | - | train |
| `train_max_epochs` | 30 | - | train |

## 4. Baselines and Controls

基线为 ResNet-18 torchvision 0.17，对照预算与指标见材料记录；比较在同一预算下进行。

## 5. Reproducibility

复现所需的代码版本、环境、数据获取与启动命令见复现清单。启动命令已在材料中给出。

## 6. Limitations

- 当批大小 64 超出单卡显存时，训练会因 OOM 中断；本结论仅适用于单卡场景。
- 当数据划分的随机种子 42 改变时，验证集指标会波动；适用范围限于固定划分下的比较。
