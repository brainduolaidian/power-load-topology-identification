# -*- coding: utf-8 -*-
"""
Q2: 拓扑识别 - 基于合成低压配电网数据 (IEEE LV Feeder 结构)
- 电压法粗分 + 电流守恒精修
- 有真值, 可计算准确率

数据来源:
  合成数据基于 IEEE European LV Test Feeder 结构特征生成
  (https://cmte.ieee.org/pes-testfeeders/resources/)
  运行 generate_lv_network.py 生成
"""
import numpy as np
import pandas as pd
import os, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, 'data')
OUT = os.path.join(BASE, 'results')
FIG = os.path.join(BASE, 'figures')
os.makedirs(OUT, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

def pearson(a, b, min_ov=100):
    m = ~(np.isnan(a) | np.isnan(b))
    if m.sum() < min_ov: return np.nan
    a1, b1 = a[m], b[m]
    if a1.std() < 1e-9 or b1.std() < 1e-9: return np.nan
    return float(np.corrcoef(a1, b1)[0, 1])

def best_shift(x, ref, lo=-20, hi=20):
    best_s, best_c = 0, -9.0
    for s in range(lo, hi+1):
        if s >= 0: a, b = x[s:], ref[:len(x)-s]
        else: a, b = x[:len(x)+s], ref[-s:]
        c = pearson(a, b, min_ov=200)
        if c is not None and c > best_c: best_c, best_s = c, s
    return best_s, best_c

# ============ 1. 加载数据 ============
print("=" * 60)
print("Q2: 拓扑识别 - 基于合成低压配电网数据")
print("=" * 60)

df = pd.read_csv(os.path.join(DATA, 'meter_data.csv'))
gt = pd.read_csv(os.path.join(DATA, 'topology_ground_truth.csv'))
tcols = [c for c in df.columns if c.startswith('t_')]
n_tp = len(tcols)
print(f"电表通道数: {len(df)}, 时间点: {n_tp}")
print(f"真值记录数: {len(gt)}")

rail_ids = df[df.meter_type == 'rail']['meter_id'].unique()
user_ids = df[df.meter_type == 'user']['meter_id'].unique()
print(f"导轨表: {len(rail_ids)}, 用户表: {len(user_ids)}")

def get_series(meter_id, channel_prefix):
    rows = df[df.meter_id == meter_id]
    for _, row in rows.iterrows():
        if row['phase'].startswith(channel_prefix):
            return row[tcols].to_numpy(float)
    return np.full(n_tp, np.nan)

rail_v = {}
rail_i = {}
for rid in rail_ids:
    rail_v[rid] = {}
    rail_i[rid] = {}
    for ph in ['a', 'b', 'c']:
        rail_v[rid][ph] = get_series(rid, f'V_{ph}')
        rail_i[rid][ph] = get_series(rid, f'I_{ph}')

user_v = {}
user_i = {}
user_phase = {}
for uid in user_ids:
    rows = df[df.meter_id == uid]
    for _, row in rows.iterrows():
        p = row['phase']
        if p.startswith('V_'):
            user_v[uid] = row[tcols].to_numpy(float)
            user_phase[uid] = p.split('_')[1]
        elif p.startswith('I_'):
            user_i[uid] = row[tcols].to_numpy(float)

# ============ 2. 时间对齐 ============
print("\n--- 时间对齐 ---")
ref_v = np.nanmedian([rail_v[r]['a'] for r in rail_ids], axis=0)
for uid in user_ids:
    s, _ = best_shift(user_v[uid], ref_v)
    if s != 0:
        user_v[uid] = np.roll(user_v[uid], s)
        user_i[uid] = np.roll(user_i[uid], s)
for rid in rail_ids:
    for ph in ['a', 'b', 'c']:
        s, _ = best_shift(rail_v[rid][ph], ref_v)
        if s != 0:
            rail_v[rid][ph] = np.roll(rail_v[rid][ph], s)
            rail_i[rid][ph] = np.roll(rail_i[rid][ph], s)
print("  对齐完成")

# ============ 3. 电压法初分配 ============
print("\n--- 电压法初分配 ---")
assignment = {}
for uid in user_ids:
    ph = user_phase.get(uid, 'a')
    scores = {}
    for rid in rail_ids:
        c = pearson(user_v[uid], rail_v[rid][ph])
        if np.isnan(c): c = -1
        scores[rid] = c
    best_rail = max(scores, key=scores.get)
    sorted_scores = sorted(scores.values(), reverse=True)
    margin = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else 1.0
    assignment[uid] = (best_rail, ph, scores[best_rail], margin)

n_correct_init = sum(1 for uid in user_ids
    if assignment[uid][0] == gt[gt.user_id == uid]['rail_id'].values[0])
print(f"  电压法准确率: {n_correct_init}/{len(user_ids)} = {n_correct_init/len(user_ids)*100:.1f}%")

# ============ 4. 电流守恒修正 ============
print("\n--- 电流守恒修正 ---")
def compute_fit(rail_id, phase):
    users_on = [uid for uid in user_ids
                if assignment[uid][0] == rail_id and assignment[uid][1] == phase]
    if not users_on:
        return np.nan, 0
    total_i = np.zeros(n_tp)
    for uid in users_on:
        if uid in user_i:
            total_i += np.nan_to_num(user_i[uid])
    return pearson(total_i, rail_i[rail_id][phase]), len(users_on)

for iteration in range(20):
    moved = False
    for uid in user_ids:
        cur_rail, cur_ph, v_score, v_margin = assignment[uid]
        if v_margin > 0.02:
            continue
        fit_before, _ = compute_fit(cur_rail, cur_ph)
        if not np.isnan(fit_before) and fit_before > 0.4:
            continue

        best_target = None
        best_corr = 0.25
        for rid in rail_ids:
            for ph in ['a', 'b', 'c']:
                if rid == cur_rail and ph == cur_ph:
                    continue
                c = pearson(user_i.get(uid, np.zeros(n_tp)), rail_i[rid][ph])
                if not np.isnan(c) and c > best_corr:
                    best_corr = c
                    best_target = (rid, ph)

        if best_target:
            assignment[uid] = (best_target[0], best_target[1], v_score, v_margin)
            moved = True

    if not moved:
        print(f"  迭代{iteration+1}: 无移动, 收敛")
        break
    else:
        n_correct = sum(1 for uid in user_ids
            if assignment[uid][0] == gt[gt.user_id == uid]['rail_id'].values[0])
        print(f"  迭代{iteration+1}: 准确率={n_correct}/{len(user_ids)}={n_correct/len(user_ids)*100:.1f}%")

# ============ 5. 置信度分级 ============
print("\n--- 置信度分级 ---")
results = []
for uid in user_ids:
    rid, ph, v_score, v_margin = assignment[uid]
    if v_margin > 0.02:
        conf = 'HIGH'
    elif v_score > 0.8:
        conf = 'MED'
    else:
        conf = 'LOW'
    gt_rail = gt[gt.user_id == uid]['rail_id'].values[0]
    gt_phase = gt[gt.user_id == uid]['phase'].values[0]
    correct = (rid == gt_rail)
    results.append({
        'user_id': uid, 'predicted_rail': rid, 'predicted_phase': ph,
        'gt_rail': gt_rail, 'gt_phase': gt_phase,
        'v_score': v_score, 'v_margin': v_margin,
        'confidence': conf, 'correct': correct
    })

result_df = pd.DataFrame(results)
result_df.to_csv(os.path.join(OUT, 'topology_result.csv'), index=False)

# ============ 6. 评估 ============
print("\n" + "=" * 60)
print("最终评估")
print("=" * 60)
acc = result_df['correct'].mean()
print(f"拓扑识别准确率: {acc*100:.1f}% ({result_df['correct'].sum()}/{len(result_df)})")

for area in gt['area_id'].unique():
    gt_users = gt[gt.area_id == area]['user_id'].values
    sub = result_df[result_df.user_id.isin(gt_users)]
    a = sub['correct'].mean()
    print(f"  {area}: {sub['correct'].sum()}/{len(sub)} = {a*100:.1f}%")

for conf in ['HIGH', 'MED', 'LOW']:
    sub = result_df[result_df.confidence == conf]
    if len(sub) > 0:
        a = sub['correct'].mean()
        print(f"  {conf}: {sub['correct'].sum()}/{len(sub)} = {a*100:.1f}%")

fit_rows = []
for rid in rail_ids:
    for ph in ['a', 'b', 'c']:
        fit, n = compute_fit(rid, ph)
        fit_rows.append({'rail_id': rid, 'phase': ph, 'fit_corr': fit, 'n_users': n})
fit_df = pd.DataFrame(fit_rows)
fit_df.to_csv(os.path.join(OUT, 'topology_fit_table.csv'), index=False)

# ============ 7. 可视化 ============
print("\n--- 生成图表 ---")

# 图1: 电压相关系数分布
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

correct_scores = result_df[result_df.correct]['v_score']
wrong_scores = result_df[~result_df.correct]['v_score']
axes[0].hist(correct_scores, bins=30, alpha=0.7, color='green', label=f'Correct (n={len(correct_scores)})')
if len(wrong_scores) > 0:
    axes[0].hist(wrong_scores, bins=30, alpha=0.7, color='red', label=f'Wrong (n={len(wrong_scores)})')
axes[0].set_xlabel('Voltage Correlation Score', fontsize=12)
axes[0].set_ylabel('Count', fontsize=12)
axes[0].set_title('Voltage Correlation Distribution', fontsize=13)
axes[0].legend(fontsize=11)

conf_counts = result_df['confidence'].value_counts()
conf_correct = result_df.groupby('confidence')['correct'].sum()
colors = {'HIGH': 'green', 'MED': 'orange', 'LOW': 'red'}
x = np.arange(len(conf_counts))
bars = axes[1].bar(x, conf_counts.values, color=[colors.get(c, 'gray') for c in conf_counts.index], alpha=0.7)
for i, (conf, count) in enumerate(conf_counts.items()):
    correct_n = conf_correct.get(conf, 0)
    axes[1].text(i, count + 1, f'{correct_n}/{count}', ha='center', fontsize=11, fontweight='bold')
axes[1].set_xticks(x)
axes[1].set_xticklabels(conf_counts.index, fontsize=11)
axes[1].set_ylabel('Count', fontsize=12)
axes[1].set_title('Confidence Level Distribution', fontsize=13)

plt.tight_layout()
plt.savefig(os.path.join(FIG, 'q2_topology_analysis.png'), dpi=150, bbox_inches='tight')
print(f"  q2_topology_analysis.png")

# 图2: 台区准确率
fig, ax = plt.subplots(figsize=(10, 5))
area_stats = []
for area in sorted(gt['area_id'].unique()):
    gt_users = gt[gt.area_id == area]['user_id'].values
    sub = result_df[result_df.user_id.isin(gt_users)]
    area_stats.append({
        'area': area,
        'total': len(sub),
        'correct': sub['correct'].sum(),
        'accuracy': sub['correct'].mean()
    })
area_df = pd.DataFrame(area_stats)
bars = ax.bar(area_df['area'], area_df['accuracy'] * 100, color='steelblue', alpha=0.7)
for i, row in area_df.iterrows():
    ax.text(i, row['accuracy'] * 100 + 1, f"{row['correct']}/{row['total']}", ha='center', fontsize=11)
ax.set_xlabel('Area', fontsize=12)
ax.set_ylabel('Accuracy (%)', fontsize=12)
ax.set_title('Topology Identification Accuracy by Area', fontsize=13)
ax.set_ylim(0, 105)
ax.axhline(y=acc * 100, color='red', linestyle='--', alpha=0.5, label=f'Overall: {acc*100:.1f}%')
ax.legend(fontsize=11)

plt.tight_layout()
plt.savefig(os.path.join(FIG, 'q2_area_accuracy.png'), dpi=150, bbox_inches='tight')
print(f"  q2_area_accuracy.png")

# ============ 8. 输出结果 ============
with open(os.path.join(OUT, 'q2_results.txt'), 'w', encoding='utf-8') as f:
    f.write("Q2: 拓扑识别 - 基于合成低压配电网数据 (IEEE LV Feeder结构)\n")
    f.write(f"导轨表: {len(rail_ids)}, 用户表: {len(user_ids)}\n")
    f.write(f"采集天数: 30天, 时间点: {n_tp}\n\n")
    f.write(f"电压法初分配准确率: {n_correct_init}/{len(user_ids)} = {n_correct_init/len(user_ids)*100:.1f}%\n")
    f.write(f"最终准确率: {acc*100:.1f}% ({result_df['correct'].sum()}/{len(result_df)})\n\n")
    f.write(f"置信度分布:\n")
    for conf in ['HIGH', 'MED', 'LOW']:
        sub = result_df[result_df.confidence == conf]
        f.write(f"  {conf}: {len(sub)} ({sub['correct'].sum()}正确)\n")
    f.write(f"\n拟合质量:\n")
    f.write(f"  中位corr: {fit_df['fit_corr'].median():.4f}\n")
    f.write(f"  >=0.5占比: {(fit_df['fit_corr'] >= 0.5).mean()*100:.1f}%\n")
    f.write(f"  >=0.8占比: {(fit_df['fit_corr'] >= 0.8).mean()*100:.1f}%\n")

print(f"\n结果已保存:")
print(f"  topology_result.csv ({len(result_df)}行)")
print(f"  topology_fit_table.csv ({len(fit_df)}行)")
print(f"  q2_results.txt")
print("\nQ2 分析完成!")
