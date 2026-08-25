# EV-CPW Dataset

## Overview

The EV Charging Power Waveform (EV-CPW) dataset contains high-resolution voltage and current waveforms captured during electric vehicle charging sessions.

- **Source**: Harvard Dataverse
- **DOI**: 10.7910/DVN/0V6YAA
- **Download URL**: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/0V6YAA
- **Sampling Rate**: 30 kHz
- **Line Frequency**: 60 Hz (North American)
- **Vehicles**: 7 EV models (BMW, Ford, Hyundai, Kia, Lexus, Mitsubishi, Nissan, Tesla, Toyota, Volvo)

## Included Samples

This repository includes a small subset (9 waveforms from 3 models) for demonstration:
- BMW iX xDrive50 (3 waveforms)
- Tesla Model 3 (3 waveforms)
- Nissan Leaf (3 waveforms)

## Full Dataset

To use the complete dataset (72 waveforms from 10 models):
1. Visit the download URL above
2. Download the EV-CPW dataset zip file
3. Extract the `EV-CPW Dataset` folder
4. Place all `Waveforms/` subdirectories into this `ev_cpw_samples/` folder

The code in `load_identification.py` will automatically scan all subdirectories for `Waveform_*.csv` files.

## File Format

Each waveform CSV file contains:
- 4 metadata header lines (Trigger Date, Time, Samples Per Cycle, Microseconds Per Sample)
- 1 column header line: `Time (ms), Voltage (V), Current (A)`
- Data rows with time, voltage, and current values

## Citation

If you use this dataset in your research, please cite the original dataset:
```
EV Charging Power Waveform (EV-CPW) Dataset, Harvard Dataverse, DOI:10.7910/DVN/0V6YAA
```
