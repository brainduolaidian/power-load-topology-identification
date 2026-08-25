[English](README.md) | [中文](README_CN.md)

# 电力负荷辨识与拓扑识别

基于**公开数据集**（EV-CPW + 合成数据）的非侵入式负荷监测（NILM）与低压台区拓扑识别算法项目。

## 项目概述

本项目实现了两个独立的电力数据分析模块：

1. **负荷辨识**：从家庭电压/电流波形中识别电动车充电事件，利用谐波域特征区分电动车充电器与笔记本电脑充电器。
2. **拓扑识别**：在无真值标注的情况下，利用电压同源性与电流守恒定律，从智能电表时序数据中恢复树状供电拓扑关系。

## 数据来源

本项目所有数据均来自公开数据集或合成生成——不含任何专有或私有数据。

| 模块 | 数据集 | 来源 | 说明 |
|------|--------|------|------|
| 负荷辨识 | EV-CPW | [Harvard Dataverse DOI:10.7910/DVN/0V6YAA](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/0V6YAA) | 电动车充电波形，30kHz，7款车型 |
| 负荷辨识 | 笔记本充电器（合成） | `generate_laptop_charger.py` 生成 | 基于 PLAID 论文特征（Gao et al., 2020） |
| 拓扑识别 | 低压配电网（合成） | `generate_lv_network.py` 生成 | 基于 IEEE European LV Test Feeder 结构 |

## 目录结构

```
GitHub项目展示/
├── load_identification/           # 模块一：负荷辨识
│   ├── code/
│   │   ├── load_identification.py      # 主算法
│   │   └── generate_laptop_charger.py  # 合成数据生成器
│   ├── data/
│   │   ├── laptop_samples/             # 20个合成笔记本充电器波形
│   │   └── ev_cpw_samples/             # EV-CPW 样本波形（9个文件，3款车型）
│   │       └── DOWNLOAD_INSTRUCTIONS.md  # 完整数据集下载说明
│   ├── results/
│   │   ├── q1_feature_table.csv        # 特征表（90个样本）
│   │   └── q1_results.txt              # 汇总结果
│   └── figures/
│       ├── q1_feature_scatter.png      # 特征散点图
│       └── q1_waveform_comparison.png  # 波形对比图
│
├── topology_identification/       # 模块二：拓扑识别
│   ├── code/
│   │   ├── topology_identification.py  # 主算法
│   │   └── generate_lv_network.py      # 合成数据生成器
│   ├── data/
│   │   ├── meter_data.csv              # 电表时序数据（3台区，15导轨表，194用户表）
│   │   ├── network_info.json           # 网络参数
│   │   └── topology_ground_truth.csv   # 拓扑真值（用于验证）
│   ├── results/
│   │   ├── topology_result.csv         # 逐用户预测结果 + 置信度
│   │   ├── topology_fit_table.csv      # 逐导轨电流守恒拟合
│   │   └── q2_results.txt              # 汇总结果
│   └── figures/
│       ├── q2_topology_analysis.png    # 电压评分 + 置信度分布
│       └── q2_area_accuracy.png        # 分台区准确率
│
├── requirements.txt
├── VERSION_NOTES.md
└── .gitignore
```

## 模块一：负荷辨识

### 算法流程

| 步骤 | 方法 | 关键结果 |
|------|------|----------|
| 周期统计 | 正斜率过零检测 + 毛刺过滤 | 30kHz/60Hz 波形精确周期计数 |
| 谐波特征提取 | 逐周期 FFT，2~9次谐波（幅度变异系数、相位标准差） | 每条波形丰富特征集 |
| 充电器分类 | 两阶段规则分类器（RMS → 谐波变异系数 → 浪涌倍数） | **89.7%**（子集） / **95.6%**（完整 EV-CPW） |

### 分类器设计

基于公开数据校准的三级顺序判据规则分类器：

1. **主判据：RMS 稳态电流** — 电动车充电器稳态电流 >5A（Level 2 充电），笔记本充电器 <1A
2. **次判据：5次谐波幅度变异系数** — 笔记本充电器 >0.30（无 PFC，负载波动），电动车 <0.20
3. **第三判据：浪涌倍数** — 笔记本充电器 >3.5倍（软启动），电动车 <2.5倍（PFC 抑制浪涌）

### 结果

**包含的样本数据**（9个 EV-CPW 样本 + 20个笔记本样本）：
```
总样本数: 29 (EV=9, 笔记本=20)
准确率: 89.7% (26/29)
混淆矩阵:
         预测EV  预测PC
  真EV       8       1
  真PC       2      18
```

**完整 EV-CPW 数据集**（70个 EV 样本 + 20个笔记本样本）：
```
总样本数: 90 (EV=70, 笔记本=20)
准确率: 95.6% (86/90)
混淆矩阵:
         预测EV  预测PC
  真EV      68       2
  真PC       2      18
```

> 准确率差异源于 EV 样本量较小。下载完整 EV-CPW 数据集可获得最佳结果。

## 模块二：拓扑识别

### 算法流程

| 步骤 | 方法 | 关键结果 |
|------|------|----------|
| 时间对齐 | 互相关平移搜索 | 所有电表对齐至参考 |
| 电压法初分配 | 按相位的用户-导轨电压 Pearson 相关系数 | 97.4% 准确率（189/194） |
| 电流守恒修正 | 对低边际用户进行门控迭代重分配 | 收敛，无退化 |
| 置信度分级 | 基于电压边际和评分的 HIGH / MED / LOW 三级 | 诚实交付质量评估 |

### 关键设计决策

- **电压法优先**：同馈线电表共享电压波动 → 高相关；跨馈线 → 低相关。给出可靠但较粗的初始分配。
- **门控修正**：仅对电压边际低且电流拟合差的用户进行重分配。门控阈值（corr > 0.25）防止随机跳转。防抖机制：拟合良好的用户不移动。
- **置信度分级**：电压边际高 → HIGH 置信度。低边际 + 中等评分 → MED。低边际 + 低评分 → LOW。

### 结果

```
导轨表: 15, 用户表: 194
电压法初分配准确率: 97.4% (189/194)
最终准确率: 97.4% (189/194)

置信度分布:
  HIGH: 189 (186正确, 98.4%)
  MED:    5 (  3正确, 60.0%)
  LOW:    0
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# --- 模块一：负荷辨识 ---
# 步骤1: 生成合成笔记本充电器波形
python load_identification/code/generate_laptop_charger.py

# 步骤2: 运行负荷辨识（使用 EV-CPW 样本 + 笔记本样本）
python load_identification/code/load_identification.py

# --- 模块二：拓扑识别 ---
# 步骤1: 生成合成低压配电网数据
python topology_identification/code/generate_lv_network.py

# 步骤2: 运行拓扑识别
python topology_identification/code/topology_identification.py
```

> **注意**：完整 EV-CPW 数据集（72条波形）的下载方式见 `load_identification/data/ev_cpw_samples/DOWNLOAD_INSTRUCTIONS.md`。

## 技术栈

- Python 3.10+
- NumPy / pandas — 数据处理
- Matplotlib — 可视化
- 标准库（os, glob, json, collections）

## 许可证

MIT
