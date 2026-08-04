# Fire Weather AI worker

`train_models.py` reproduces and corrects the three prediction tasks developed during the internship. It calculates the three-hour pressure-change feature before sampling, creates train/validation/test splits for rare-event classifiers, selects a decision threshold on validation data, reports held-out metrics, and saves versioned joblib bundles plus `models/manifest.json`.

`ml_service.py` is the standalone Flask inference program. It loads the three saved models once at startup and accepts one event per `POST /predict`. It listens on `127.0.0.1:5001` by default.

From the project root:

```powershell
python .\ai_worker\train_models.py --max-samples 100000
python .\ai_worker\ml_service.py
python -m unittest ai_worker.test_ml_service -v
```

The training CSV is in `../docs/datasets`, as required by the final package structure. The pressure-risk task normally uses PostgreSQL to retrieve the previous valid pressure observation for the submitted device; set `POSTGRES_DSN` before starting the service.