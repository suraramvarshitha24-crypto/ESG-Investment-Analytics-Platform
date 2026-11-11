# ESG Investment Analytics Platform

A student-friendly Flask project using the provided company ESG and financial CSV dataset. The code is kept in small functions so the project can be explained during a demonstration or viva.

## Project structure

```text
ESG_VSCode_Project/
├── app.py
├── requirements.txt
├── data/company_esg_financial_dataset.csv
├── templates/index.html
└── static/
    ├── css/style.css
    └── js/app.js
```

## Run on Windows in VS Code

1. Install Python and the VS Code Python extension.
2. Extract this ZIP and open the `ESG_VSCode_Project` folder in VS Code.
3. Open **Terminal → New Terminal**.
4. Create a virtual environment:

   ```powershell
   py -m venv .venv
   ```

5. Activate it:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run the commands below using `.\.venv\Scripts\python.exe` instead of `python`.

6. Install dependencies (the ML and SHAP libraries are larger than the original dashboard dependencies):

   ```powershell
   python -m pip install -r requirements.txt
   ```

7. Start the app:

   ```powershell
   python app.py
   ```

8. Open `http://127.0.0.1:5000` in your browser. Keep the terminal open while using the app. Press **Ctrl+C** to stop it.

The first start trains three small demonstration models and may take a little longer than the original dashboard.

## Features

- Dashboard summary, ESG category chart, top company records, industry analysis, company search, and searchable/paginated dataset table.
- Weighted ESG score using the proposal formula: `0.4 × E + 0.3 × S + 0.3 × G`.
- Company ranking using each company's latest available year.
- Comparison of 2–5 companies.
- Portfolio ESG score calculator. Enter company weights that add up to 100%.
- Three simple classification models: Logistic Regression, Decision Tree, and Random Forest.
- Model evaluation using accuracy, precision, recall, and F1-score.
- SHAP explanation for a selected company's model prediction when SHAP runs successfully. If it fails, the app displays Random Forest feature importance instead.
- Downloadable CSV report of the latest available record for each company.

## Important research limitation

The supplied CSV does **not** contain an independent, verified ESG-risk label. To demonstrate the ML workflow, the app creates a proxy label from the weighted ESG score bands described in the project guidance: score 80 or above = Low Risk, 60 to below 80 = Medium Risk, below 60 = High Risk. The models use financial and operational columns rather than the E/S/G score columns as input features, and the train/test split keeps company groups separate.

This is a classroom classification demonstration, not proof of future ESG risk. The model metrics describe how well the models reproduce the proxy labels. In the report and viva, explain this limitation honestly. For a stronger research result, replace the proxy labels with a documented, independent risk label from a suitable source.

## API routes

- `GET /api/summary`
- `GET /api/top-companies`
- `GET /api/ranking?limit=20`
- `GET /api/companies`
- `GET /api/industries`
- `GET /api/industry?name=Retail`
- `GET /api/company?name=Company_1`
- `GET /api/compare?companies=Company_1,Company_2`
- `POST /api/portfolio` with JSON `{"holdings":[{"company":"Company_1","weight":50},{"company":"Company_2","weight":50}]}`
- `GET /api/ml/metrics`
- `GET /api/ml/predict?company=Company_1`
- `GET /api/records?page=1&per_page=25&search=retail`
- `GET /api/esg-distribution`
- `GET /api/report.csv`

## Scope not yet included

This local version still reads data directly from the CSV. It does not yet implement login/user management or a MySQL database. Those modules are mentioned in the written project report, so confirm with the project guide whether they are mandatory for the final demo before spending time on them. A CSV-backed prototype is simpler to set up and explain, but should not be described as a database-backed system.
