# -*- coding: utf-8 -*-
"""
生成合成低压配电网电表数据

基于 IEEE European LV Test Feeder 结构特征:
- 1个变压器/台区 -> 多条馈线(导轨表) -> 多个用户表
- 电压同源性: 同馈线电压强相关, 跨馈线弱相关
- 电流守恒: 导轨电流 = sum(用户电流) + 线损
- 已知拓扑真值, 可真正验证算法准确率

参考: IEEE PES Test Feeder: https://cmte.ieee.org/pes-testfeeders/resources/
"""
import numpy as np
import pandas as pd
import os, json

np.random.seed(42)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, 'data')
os.makedirs(OUT, exist_ok=True)

N_AREAS = 3
RAILS_PER_AREA = [5, 4, 6]
USERS_PER_RAIL_RANGE = (8, 20)
N_DAYS = 30
INTERVAL_MIN = 15
POINTS_PER_DAY = 1440 // INTERVAL_MIN
N_TIMEPOINTS = N_DAYS * POINTS_PER_DAY

VOLTAGE_BASE = 230.0
FREQ = 50.0

print(f"=== 合成低压配电网参数 ===")
print(f"台区数: {N_AREAS}")
print(f"导轨表总数: {sum(RAILS_PER_AREA)}")
print(f"采集天数: {N_DAYS}天, 间隔: {INTERVAL_MIN}分钟")
print(f"总时间点: {N_TIMEPOINTS}")
print()

meters = []
rail_id_list = []
user_meters = []
ground_truth = []

meter_id_counter = 1000

for area_idx in range(N_AREAS):
    area_id = f"area_{area_idx+1:03d}"
    n_rails = RAILS_PER_AREA[area_idx]

    rail_voltages = VOLTAGE_BASE + np.random.randn(n_rails) * 1.5
    rail_impedances = 0.3 + np.random.rand(n_rails) * 0.4

    for rail_idx in range(n_rails):
        rail_id = f"rail_{meter_id_counter:04d}"
        meter_id_counter += 1
        rail_id_list.append(rail_id)

        for phase in ['a', 'b', 'c']:
            meters.append((area_id, rail_id, 'rail', rail_id, phase,
                           rail_voltages[rail_idx], rail_impedances[rail_idx]))

        n_users = np.random.randint(*USERS_PER_RAIL_RANGE)
        for u in range(n_users):
            user_id = f"user_{meter_id_counter:04d}"
            meter_id_counter += 1

            phase = np.random.choice(['a', 'b', 'c'])
            meters.append((area_id, user_id, 'user', rail_id, phase,
                           rail_voltages[rail_idx], rail_impedances[rail_idx]))
            user_meters.append(user_id)
            ground_truth.append((user_id, rail_id, area_id, phase))

rail_meters = list(set(rail_id_list))
print(f"导轨表: {len(rail_meters)}个")
print(f"用户表: {len(user_meters)}个")
print(f"总记录: {len(meters)}条")
print()

t = np.arange(N_TIMEPOINTS)
daily_pattern = 2.0 * np.sin(2 * np.pi * t / POINTS_PER_DAY - np.pi/2)
weekly_pattern = 0.5 * np.sin(2 * np.pi * t / (7 * POINTS_PER_DAY))
global_voltage_noise = np.random.randn(N_TIMEPOINTS) * 0.3
global_voltage = daily_pattern + weekly_pattern + global_voltage_noise

rail_voltage_noise = {}
for r in rail_meters:
    rail_load = 1.5 * np.sin(2 * np.pi * t / POINTS_PER_DAY + np.random.uniform(0, 2*np.pi))
    rail_noise = np.random.randn(N_TIMEPOINTS) * 0.4
    rail_voltage_noise[r] = rail_load + rail_noise

user_loads = {}
for m in meters:
    if m[2] == 'user':
        uid = m[1]
        base_power = np.random.uniform(0.5, 5.0)
        morning_peak = base_power * 0.8 * np.exp(-((t % POINTS_PER_DAY - 30)**2) / 200)
        evening_peak = base_power * 1.2 * np.exp(-((t % POINTS_PER_DAY - 75)**2) / 300)
        events = np.zeros(N_TIMEPOINTS)
        for _ in range(np.random.randint(5, 20)):
            start = np.random.randint(0, N_TIMEPOINTS - 10)
            duration = np.random.randint(2, 15)
            magnitude = np.random.uniform(0.3, 2.0)
            events[start:start+duration] += magnitude
        standby = base_power * 0.15
        noise = np.random.randn(N_TIMEPOINTS) * base_power * 0.05
        user_loads[uid] = np.maximum(0.01, standby + morning_peak + evening_peak + events + noise)

print("生成电表数据...")
meter_data = {}

for area_id, meter_id, mtype, rail_id, phase, v_base, z_rail in meters:
    v = v_base + global_voltage + rail_voltage_noise[rail_id]
    if mtype == 'user':
        v += np.random.randn(N_TIMEPOINTS) * 0.15
    else:
        v += np.random.randn(N_TIMEPOINTS) * 0.05

    if mtype == 'user':
        power = user_loads.get(meter_id, np.ones(N_TIMEPOINTS) * 0.5)
        current = power / (v + 1e-6)
    else:
        rail_users = [m2 for m2 in meters if m2[3] == rail_id and m2[2] == 'user' and m2[4] == phase]
        total_current = np.zeros(N_TIMEPOINTS)
        for u in rail_users:
            uid = u[1]
            if uid in meter_data:
                total_current += meter_data[uid][1]
            elif uid in user_loads:
                total_current += user_loads[uid] / (v + 1e-6)
        line_loss = 0.03 * total_current + np.random.randn(N_TIMEPOINTS) * 0.1
        current = total_current + line_loss

    meter_data[meter_id] = (v, current)

print("写入 meter_data.csv ...")
header = ['meter_id', 'area_id', 'meter_type', 'phase']
time_cols = [f't_{i}' for i in range(N_TIMEPOINTS)]
header += time_cols

rows = []
for area_id, meter_id, mtype, rail_id, phase, _, _ in meters:
    v, i = meter_data[meter_id]
    rows.append([meter_id, area_id, mtype, f'V_{phase}'] + list(v))
    rows.append([meter_id, area_id, mtype, f'I_{phase}'] + list(i))

df = pd.DataFrame(rows, columns=header)
df.to_csv(os.path.join(OUT, 'meter_data.csv'), index=False)
print(f"  meter_data.csv: {df.shape[0]}行, {df.shape[1]}列")

gt_df = pd.DataFrame(ground_truth, columns=['user_id', 'rail_id', 'area_id', 'phase'])
gt_df.to_csv(os.path.join(OUT, 'topology_ground_truth.csv'), index=False)
print(f"  topology_ground_truth.csv: {len(gt_df)}条真值")

stats = {
    'n_areas': N_AREAS,
    'n_rails': len(rail_meters),
    'n_users': len(user_meters),
    'n_days': N_DAYS,
    'interval_min': INTERVAL_MIN,
    'n_timepoints': N_TIMEPOINTS,
    'voltage_base': VOLTAGE_BASE,
    'freq': FREQ,
}
with open(os.path.join(OUT, 'network_info.json'), 'w') as f:
    json.dump(stats, f, indent=2)
print(f"  network_info.json")

print(f"\n=== 合成配电网数据生成完成 ===")
print(f"路径: {OUT}")
print(f"台区: {N_AREAS}, 导轨: {len(rail_meters)}, 用户: {len(user_meters)}")
print(f"时间跨度: {N_DAYS}天, {N_TIMEPOINTS}个时间点")
