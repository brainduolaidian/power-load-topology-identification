# -*- coding: utf-8 -*-
"""
生成合成笔记本充电器波形数据
基于 PLAID 论文公开特征 (Gao et al., Scientific Data, 2020)
- 采样率 30kHz, 60Hz, 每周期 500 点
- 有PFC: 电流近似正弦, THD < 15%
- 功率 60-90W, 电流幅值 0.5-0.8A peak
- 软启动: 浪涌倍数 2-4 倍
- 5次谐波幅度变异系数低 (<0.22)

输出格式兼容 EV-CPW CSV 格式, 可直接被 load_identification.py 读取
"""
import numpy as np
import os

np.random.seed(2024)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, 'data', 'laptop_samples')
os.makedirs(OUT, exist_ok=True)

FS = 30000.0
F_LINE = 60.0
N_CYCLES = 5
N_PER_CYCLE = int(FS / F_LINE)
N_TOTAL = N_CYCLES * N_PER_CYCLE
US_PER_SAMPLE = 1e6 / FS

V_PEAK = 170.0
T_MS = np.arange(N_TOTAL) / FS * 1000.0 - N_CYCLES / F_LINE * 1000.0 / 2

for i in range(20):
    power = np.random.uniform(60, 90)
    i_rms = power / 120.0
    i_peak = i_rms * np.sqrt(2)

    inrush_mult = np.random.uniform(2.0, 4.0)
    n_inrush = int(0.3 * N_PER_CYCLE)
    inrush_decay = np.exp(-np.arange(n_inrush) / (n_inrush * 0.3))

    phase_offset = np.random.uniform(-0.1, 0.1)
    i_fundamental = i_peak * np.sin(2 * np.pi * F_LINE * np.arange(N_TOTAL) / FS + phase_offset)

    h3_amp = i_peak * np.random.uniform(0.02, 0.08)
    h5_amp = i_peak * np.random.uniform(0.01, 0.05)
    h7_amp = i_peak * np.random.uniform(0.005, 0.03)
    i_harmonic = (h3_amp * np.sin(3 * 2 * np.pi * F_LINE * np.arange(N_TOTAL) / FS) +
                  h5_amp * np.sin(5 * 2 * np.pi * F_LINE * np.arange(N_TOTAL) / FS + np.random.uniform(0, 2*np.pi)) +
                  h7_amp * np.sin(7 * 2 * np.pi * F_LINE * np.arange(N_TOTAL) / FS))

    i_inrush = np.zeros(N_TOTAL)
    i_inrush[:n_inrush] = i_peak * inrush_mult * inrush_decay

    noise = np.random.randn(N_TOTAL) * i_peak * 0.02

    current = i_fundamental + i_harmonic + i_inrush + noise
    current = current[:N_TOTAL]

    v_noise = np.random.randn(N_TOTAL) * 0.5
    v_h3 = V_PEAK * 0.01 * np.sin(3 * 2 * np.pi * F_LINE * np.arange(N_TOTAL) / FS)
    voltage = V_PEAK * np.sin(2 * np.pi * F_LINE * np.arange(N_TOTAL) / FS) + v_h3 + v_noise

    fname = os.path.join(OUT, f"laptop_sample_{i+1:02d}.csv")
    with open(fname, 'w') as f:
        f.write(f"Trigger_Date,2024/01/{15+i}\n")
        f.write(f"Trigger_Time,T 10:{30+i}:00.000\n")
        f.write(f"Samples_Per_Cycle,{N_PER_CYCLE}\n")
        f.write(f"Microseconds_Per_Sample,{US_PER_SAMPLE:.3f}\n")
        f.write("Time (ms),Voltage (V),Current (A)\n")
        for j in range(N_TOTAL):
            f.write(f"{T_MS[j]:.2f},{voltage[j]:.3f},{current[j]:.3f}\n")

    print(f"  laptop_sample_{i+1:02d}.csv  (power={power:.0f}W, inrush={inrush_mult:.1f}x, h5_amp={h5_amp:.4f})")

print(f"\n生成完成: 20个笔记本充电器样本")
print(f"路径: {OUT}")
