# Dentex Dataset Deduplication Map

Generated: 2026-10-10

## Central artefacts

### mega-dataset.zip (SHA256 DB412C0FCE234ECF0D7156A9AA46BDEAB37E38E5F0AA0FE7ADABC1357DE5E0D8)
Central copy:
- C:\Users\PC1\Desktop\dental-ai\mega-dataset.zip

References (junctions/symlinks):
- dental-ai-v2\kaggle\night\mega5_ds\mega-dataset.zip.bak (renamed, original removed)
- dental-ai-v3\kaggle\night\mega5_ds\mega-dataset.zip → symlink to central (attempted, fallback to .bak)
- dental-ai-v4\kaggle\night\mega5_ds\mega-dataset.zip → symlink to central (attempted, fallback to .bak)

Note: Symlink creation requires admin privilege. Current state: v2/v3/v4 backups renamed to .bak and junctions for night folder created.

### dentex_night.zip (SHA256 77D5A5342876F4F500AA3A64F05B20622A2D4BF43E8509403A9E1C51D596A79B)
Central copy:
- C:\Users\PC1\Desktop\dental-ai-v2\kaggle\night\dentex_night.zip (3.8 GB)

Deduplicated:
- Removed C:\Users\PC1\Desktop\dental-ai-v3\kaggle\night\dentex_night.zip (duplicate)
- Removed C:\Users\PC1\Desktop\dental-ai-v4\kaggle\night\dentex_night.zip (duplicate)

Folder junctions:
- C:\Users\PC1\Desktop\dental-ai-v3\kaggle\night → junction → C:\Users\PC1\Desktop\dental-ai-v2\kaggle\night
- C:\Users\PC1\Desktop\dental-ai-v4\kaggle\night → junction → C:\Users\PC1\Desktop\dental-ai-v2\kaggle\night

### training_data.zip (SHA256 18B2A2DBC5A2B10B0CC6A7677C46A382F4709AB8C9C3BB94F57B74E38E11FFD3)
Only in dental-ai:
- C:\Users\PC1\Desktop\dental-ai\datasets\dentex\DENTEX\training_data.zip (10.9 GB)

No duplicates found.

## Project inventory

### dental-ai
- Size: ~53 GB
- Key datasets: datasets\dentex\DENTEX (24.7 GB), combined-dataset (302 MB), combined-dataset-v2 (959 MB), mega-dataset (719 MB)
- Contains full DENTEX extraction.

### dental-ai-v2
- Size: ~14.6 GB
- Night folder now central for dentex_night
- Backend/frontend variant with dual-model integration.

### dental-ai-v3
- Size: ~7.3 GB
- Now references v2 night folder via junction.

### dental-ai-v4
- Size: ~10.0 GB
- Now references v2 night folder via junction.

## Actions taken
1. Identified SHA256 duplicates for mega-dataset.zip and dentex_night.zip.
2. Renamed duplicate mega-dataset.zip files to *.bak.
3. Removed duplicate dentex_night.zip from v3/v4.
4. Created NTFS junctions for kaggle\night in v3/v4 → v2.
5. Documented map.

## Recommendations
- Keep all future heavy datasets under C:\Users\PC1\Desktop\dental-ai\archive\ and use junctions/symlinks in variants.
- For mega-dataset, keep single canonical copy in dental-ai and reference via junction where needed.
- Review torch DLL duplicates (torch_cuda.dll, cuDNN etc.) – they are identical across versions but part of .venv; can be left as is or moved to shared env.
