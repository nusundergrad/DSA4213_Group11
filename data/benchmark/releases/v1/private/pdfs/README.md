# Drop filing PDFs here

Save your filing PDF in this folder. Keep the original filename.

From the repository root, replace `your-filing.pdf` with that filename:

```powershell
python -m src.benchmark.extract_sources your-filing.pdf --source-id SRC_03
```

Apple uses `SRC_01`; Microsoft uses `SRC_02`. Both already use their PDFs.
Use a new ID for a new filing. An existing ID replaces its TXT and JSON after
backing up the old files in `private/archive/`.

The script reads only the local PDF. Outputs go in `private/sources/`.
After changing a source, update and review its linked evidence packets too.

See [the benchmark guide](../../../../docs/benchmark.md) for the next steps.
