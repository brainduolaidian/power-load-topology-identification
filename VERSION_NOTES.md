# Version Notes

## v2.0 (2026-08-25) — Public Dataset Edition

### Breaking Changes
- Replaced all proprietary/enterprise data with public datasets
- All code paths changed to relative paths (portable across machines)
- Data generation scripts included for full reproducibility

### Data Sources
- **EV-CPW**: Public EV charging waveform dataset from Harvard Dataverse (DOI:10.7910/DVN/0V6YAA)
- **Laptop charger (synthetic)**: Generated based on PLAID paper features (Gao et al., Scientific Data, 2020)
- **LV network (synthetic)**: Generated based on IEEE European LV Test Feeder structure

### Module 1: Load Identification
- Adapted classifier thresholds for public data characteristics
- Added RMS steady current as primary criterion (EV >5A vs laptop <1A)
- Achieved 95.6% accuracy (86/90) on EV-CPW + synthetic laptop data
- Added inline figure generation (scatter plot + waveform comparison)

### Module 2: Topology Identification
- Simplified from 12 version iterations to single clean implementation
- Voltage method + gated current conservation refinement
- Achieved 97.4% accuracy (189/194) on synthetic LV network data
- Added inline figure generation (score distribution + area accuracy)

### Removed (from v1.0)
- All proprietary waveform data files
- All enterprise identifiers (real meter IDs, area names, user IDs)
- Multi-version iteration history (consolidated into clean final versions)
- Scikit-learn dependency (rule classifier needs no ML library)

## v1.0 (Original)

- Based on proprietary enterprise data (not included)
- 8 version iterations for load identification
- 12 version iterations for topology identification
- Achieved 100% accuracy on proprietary data
