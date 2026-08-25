# -*- coding: utf-8 -*-
"""
Q1: 负荷辨识 - 基于公开数据集 (EV-CPW + 合成笔记本充电器)
- 周期统计
- 谐波特征提取
- 充电器分类 (EV vs Laptop)

数据来源:
  EV-CPW: 电动车充电波形, Harvard Dataverse (https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/0V6YAA)
  笔记本充电器: 基于PLAID论文特征合成 (Gao et al., Scientific Data, 2020)

运行前请确保:
  1. data/laptop_samples/ 目录下有合成笔记本波形 (运行 generate_laptop_charger.py 生成)
  2. data/ev_cpw_samples/ 目录下有EV-CPW波形 (从Harvard Dataverse下载, 或运行 download_evcpw.py)
"""
import numpy as np
import pandas as pd
import os, json, glob
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_EV = os.path.join(BASE, 'data', 'ev_cpw_samples')
DATA_PC = os.path.join(BASE, 'data', 'laptop_samples')
OUT = os.path.join(BASE, 'results')
FIG = os.path.join(BASE, 'figures')
os.makedirs(OUT, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

def read_waveform(filepath):
    """读取 EV-CPW 格式波形文件（跳过4行元数据）。"""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    meta = {}
    for line in lines[:4]:
        parts = line.strip().split(',')
        if len(parts) >= 2:
            meta[parts[0]] = parts[1]
    data_lines = lines[5:]
    t, v, i = [], [], []
    for line in data_lines:
        parts = line.strip().split(',')
        if len(parts) >= 3:
            try:
                t.append(float(parts[0]))
                v.append(float(parts[1]))
                i.append(float(parts[2]))
            except ValueError:
                continue
    return np.array(v), np.array(i), meta

def count_cycles(v, fs=30000.0, f_line=60.0):
    """正斜率过零检测统计周期。"""
    s = np.sign(v)
    zc = np.where((s[:-1] < 0) & (s[1:] >= 0))[0] + 1
    if len(zc) < 2:
        return 0, np.array([])
    periods = np.diff(zc)
    ideal = int(fs / f_line)
    valid = (periods >= ideal * 0.8) & (periods <= ideal * 1.2)
    periods = periods[valid]
    return len(periods), periods

def extract_harmonics(v, i, fs=30000.0, f_line=60.0, n_harmonics=9):
    """提取谐波特征（逐周期FFT）。"""
    n_per_cycle = int(fs / f_line)
    s = np.sign(v)
    zc = np.where((s[:-1] < 0) & (s[1:] >= 0))[0] + 1
    if len(zc) < 3:
        return None

    amps = {h: [] for h in range(2, n_harmonics+1)}
    phases = {h: [] for h in range(2, n_harmonics+1)}

    for j in range(len(zc) - 1):
        start, end = zc[j], zc[j+1]
        if end - start < n_per_cycle * 0.5:
            continue
        seg_i = i[start:end]
        if len(seg_i) < 10:
            continue
        N = len(seg_i)
        fft = np.fft.rfft(seg_i)
        freqs = np.fft.rfftfreq(N, 1/fs)

        for h in range(2, n_harmonics+1):
            target_freq = h * f_line
            idx = np.argmin(np.abs(freqs - target_freq))
            if idx < len(fft):
                amp = 2 * np.abs(fft[idx]) / N
                phase = np.angle(fft[idx])
                amps[h].append(amp)
                phases[h].append(phase)

    result = {}
    for h in range(2, n_harmonics+1):
        a = np.array(amps[h])
        p = np.array(phases[h])
        if len(a) > 0:
            result[f'h{h}_amp_mean'] = np.mean(a)
            result[f'h{h}_amp_cv'] = np.std(a) / (np.mean(a) + 1e-12)
            result[f'h{h}_phase_std'] = np.std(p)
        else:
            result[f'h{h}_amp_mean'] = 0
            result[f'h{h}_amp_cv'] = 0
            result[f'h{h}_phase_std'] = 0

    result['ampcv_h5'] = result.get('h5_amp_cv', 0)
    result['phstd_h5'] = result.get('h5_phase_std', 0)

    rms_steady = np.sqrt(np.mean(i[n_per_cycle*2:]**2)) if len(i) > n_per_cycle*2 else np.sqrt(np.mean(i**2))
    rms_peak = np.max(np.abs(i[:n_per_cycle])) if len(i) > n_per_cycle else np.max(np.abs(i))
    result['inrush_ratio'] = rms_peak / (rms_steady + 1e-6)
    result['rms_steady'] = rms_steady

    return result

# ============ 1. 加载数据 ============
print("=" * 60)
print("Q1: 负荷辨识 - 基于公开数据集 (EV-CPW + 合成笔记本充电器)")
print("=" * 60)

ev_files = glob.glob(os.path.join(DATA_EV, "**", "Waveform_*.csv"), recursive=True)
if not ev_files:
    ev_files = glob.glob(os.path.join(DATA_EV, "**", "*.csv"), recursive=True)
pc_files = sorted(glob.glob(os.path.join(DATA_PC, "laptop_sample_*.csv")))

print(f"\nEV-CPW 波形文件: {len(ev_files)}个")
print(f"合成笔记本波形: {len(pc_files)}个")

if len(ev_files) == 0:
    print("\n[警告] 未找到EV-CPW波形文件!")
    print(f"  请将EV-CPW波形CSV文件放入: {DATA_EV}")
    print("  下载地址: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/0V6YAA")
if len(pc_files) == 0:
    print("\n[警告] 未找到合成笔记本波形!")
    print(f"  请先运行: python code/generate_laptop_charger.py")

if len(ev_files) == 0 or len(pc_files) == 0:
    print("\n数据不足, 无法继续分析。请按上述提示准备数据。")
    exit(1)

# ============ 2. 周期统计 ============
print("\n--- 周期统计 ---")
cycle_results = []
for f in ev_files[:5]:
    v, i, meta = read_waveform(f)
    n, periods = count_cycles(v)
    name = os.path.basename(os.path.dirname(f))
    if len(periods) > 0:
        from collections import Counter
        dist = dict(sorted(Counter(periods.tolist()).items()))
        print(f"  {name}: {n}周期, 分布={dist}, 平均={np.mean(periods):.1f}")
        cycle_results.append({'file': name, 'n_cycles': n, 'mean': np.mean(periods), 'dist': str(dist)})

for f in pc_files[:5]:
    v, i, meta = read_waveform(f)
    n, periods = count_cycles(v)
    name = os.path.basename(f)
    if len(periods) > 0:
        from collections import Counter
        dist = dict(sorted(Counter(periods.tolist()).items()))
        print(f"  {name}: {n}周期, 分布={dist}, 平均={np.mean(periods):.1f}")
        cycle_results.append({'file': name, 'n_cycles': n, 'mean': np.mean(periods), 'dist': str(dist)})

# ============ 3. 特征提取 ============
print("\n--- 谐波特征提取 ---")
all_features = []

for f in ev_files:
    v, i, meta = read_waveform(f)
    feat = extract_harmonics(v, i)
    if feat:
        feat['label'] = 'EV'
        feat['source'] = os.path.basename(os.path.dirname(f))
        feat['file'] = os.path.basename(f)
        all_features.append(feat)

for f in pc_files:
    v, i, meta = read_waveform(f)
    feat = extract_harmonics(v, i)
    if feat:
        feat['label'] = 'PC'
        feat['source'] = 'synthetic'
        feat['file'] = os.path.basename(f)
        all_features.append(feat)

df = pd.DataFrame(all_features)
print(f"  总样本数: {len(df)} (EV={len(df[df.label=='EV'])}, PC={len(df[df.label=='PC'])})")

# ============ 4. 分类 ============
print("\n--- 规则分类器 ---")

def classify(row):
    """两阶段规则分类器（基于公开数据特征校准）
    EV-CPW的Level 2 EV充电器: 高功率(20-30A)、低浪涌(有PFC)、低谐波波动
    合成笔记本充电器: 低功率(<1A)、高浪涌(无PFC)、高谐波波动
    """
    # 主判据: RMS稳态电流 (EV >> 5A, PC < 1A)
    if row['rms_steady'] > 5.0:
        return 'EV'
    # 次判据: 5次谐波变异系数 (PC波动大 > 0.30, EV稳定 < 0.20)
    elif row['ampcv_h5'] > 0.30:
        return 'PC'
    # 第三判据: 浪涌倍数 (PC软启动差 > 3.5, EV有PFC < 2.5)
    elif row['inrush_ratio'] > 3.5:
        return 'PC'
    else:
        return 'EV'

df['predicted'] = df.apply(classify, axis=1)
df['correct'] = df['label'] == df['predicted']

acc = df['correct'].mean()
print(f"  准确率: {acc*100:.1f}% ({df['correct'].sum()}/{len(df)})")
print(f"  EV召回率: {(df[df.label=='EV']['correct']).mean()*100:.1f}%")
print(f"  PC召回率: {(df[df.label=='PC']['correct']).mean()*100:.1f}%")

tp = len(df[(df.label=='EV') & (df.predicted=='EV')])
fp = len(df[(df.label=='PC') & (df.predicted=='EV')])
tn = len(df[(df.label=='PC') & (df.predicted=='PC')])
fn = len(df[(df.label=='EV') & (df.predicted=='PC')])
print(f"\n  混淆矩阵:")
print(f"  预测EV  预测PC")
print(f"  真EV   {tp:5d}  {fn:5d}")
print(f"  真PC   {fp:5d}  {tn:5d}")

# ============ 5. 特征统计 ============
print("\n--- 特征统计 ---")
for label in ['EV', 'PC']:
    sub = df[df.label == label]
    print(f"\n  {label} (n={len(sub)}):")
    for col in ['ampcv_h5', 'inrush_ratio', 'phstd_h5', 'rms_steady']:
        vals = sub[col]
        print(f"    {col}: {vals.mean():.4f} ± {vals.std():.4f} (range: {vals.min():.4f}~{vals.max():.4f})")

# ============ 6. 可视化 ============
print("\n--- 生成图表 ---")

# 图1: 特征散点图
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

ax = axes[0]
ev_df = df[df.label == 'EV']
pc_df = df[df.label == 'PC']
ax.scatter(ev_df['rms_steady'], ev_df['ampcv_h5'], c='blue', label='EV', alpha=0.6, s=30)
ax.scatter(pc_df['rms_steady'], pc_df['ampcv_h5'], c='red', label='Laptop', alpha=0.6, s=30, marker='^')
ax.set_xlabel('RMS Steady Current (A)', fontsize=12)
ax.set_ylabel('5th Harmonic Amplitude CV', fontsize=12)
ax.set_title('Feature Separation: RMS vs Harmonic CV', fontsize=13)
ax.legend(fontsize=11)
ax.axhline(y=0.30, color='gray', linestyle='--', alpha=0.5)
ax.axvline(x=5.0, color='gray', linestyle='--', alpha=0.5)
ax.set_xlim(-0.5, 30)

ax = axes[1]
ax.scatter(ev_df['inrush_ratio'], ev_df['ampcv_h5'], c='blue', label='EV', alpha=0.6, s=30)
ax.scatter(pc_df['inrush_ratio'], pc_df['ampcv_h5'], c='red', label='Laptop', alpha=0.6, s=30, marker='^')
ax.set_xlabel('Inrush Ratio', fontsize=12)
ax.set_ylabel('5th Harmonic Amplitude CV', fontsize=12)
ax.set_title('Feature Separation: Inrush vs Harmonic CV', fontsize=13)
ax.legend(fontsize=11)
ax.axhline(y=0.30, color='gray', linestyle='--', alpha=0.5)
ax.axvline(x=3.5, color='gray', linestyle='--', alpha=0.5)

plt.tight_layout()
plt.savefig(os.path.join(FIG, 'q1_feature_scatter.png'), dpi=150, bbox_inches='tight')
print(f"  q1_feature_scatter.png")

# 图2: 波形对比示例
fig, axes = plt.subplots(2, 1, figsize=(12, 8))

if len(ev_files) > 0:
    v_ev, i_ev, _ = read_waveform(ev_files[0])
    t_ev = np.arange(len(i_ev)) / 30000.0 * 1000.0
    axes[0].plot(t_ev[:1500], i_ev[:1500], 'b-', linewidth=0.5)
    axes[0].set_ylabel('Current (A)', fontsize=11)
    axes[0].set_title('EV Charger Waveform (EV-CPW Dataset)', fontsize=12)
    axes[0].grid(True, alpha=0.3)

if len(pc_files) > 0:
    v_pc, i_pc, _ = read_waveform(pc_files[0])
    t_pc = np.arange(len(i_pc)) / 30000.0 * 1000.0
    axes[1].plot(t_pc[:1500], i_pc[:1500], 'r-', linewidth=0.5)
    axes[1].set_ylabel('Current (A)', fontsize=11)
    axes[1].set_xlabel('Time (ms)', fontsize=11)
    axes[1].set_title('Laptop Charger Waveform (Synthetic)', fontsize=12)
    axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(FIG, 'q1_waveform_comparison.png'), dpi=150, bbox_inches='tight')
print(f"  q1_waveform_comparison.png")

# ============ 7. 输出结果 ============
df.to_csv(os.path.join(OUT, 'q1_feature_table.csv'), index=False)
print(f"\n特征表已保存: q1_feature_table.csv")

with open(os.path.join(OUT, 'q1_results.txt'), 'w', encoding='utf-8') as f:
    f.write("Q1: 负荷辨识 - 基于公开数据集 (EV-CPW + 合成笔记本)\n")
    f.write(f"EV样本: {len(df[df.label=='EV'])}个 (来自EV-CPW数据集, 7款EV车型)\n")
    f.write(f"PC样本: {len(df[df.label=='PC'])}个 (基于PLAID论文特征合成)\n")
    f.write(f"\n规则分类器结果:\n")
    f.write(f"  准确率: {acc*100:.1f}% ({df['correct'].sum()}/{len(df)})\n")
    f.write(f"  混淆矩阵: TP={tp}, FP={fp}, TN={tn}, FN={fn}\n")
    f.write(f"\n关键判据（基于公开数据校准）:\n")
    f.write(f"  rms_steady阈值=5.0A: EV均值={df[df.label=='EV']['rms_steady'].mean():.2f}A, PC均值={df[df.label=='PC']['rms_steady'].mean():.2f}A\n")
    f.write(f"  ampcv_h5阈值=0.30: EV均值={df[df.label=='EV']['ampcv_h5'].mean():.4f}, PC均值={df[df.label=='PC']['ampcv_h5'].mean():.4f}\n")
    f.write(f"  inrush_ratio阈值=3.5: EV均值={df[df.label=='EV']['inrush_ratio'].mean():.2f}, PC均值={df[df.label=='PC']['inrush_ratio'].mean():.2f}\n")
print("结果已保存: q1_results.txt")
print("\nQ1 分析完成!")
