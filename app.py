"""ESG Investment Analytics Platform.

Student-friendly Flask application. The CSV file is the project's data source;
Pandas handles data cleaning and calculations, and scikit-learn handles the
risk-classification demonstration.
"""
from pathlib import Path
from io import BytesIO

import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "company_esg_financial_dataset.csv"
app = Flask(__name__)

ESG_COLUMNS = ["ESG_Environmental", "ESG_Social", "ESG_Governance"]
# These are available financial/operational fields, not the ESG scores themselves.
ML_FEATURES = [
    "Revenue", "ProfitMargin", "MarketCap", "GrowthRate",
    "CarbonEmissions", "WaterUsage", "EnergyConsumption"
]


def load_dataset():
    """Read the CSV, check important columns, clean it, and calculate ESG scores."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    data = pd.read_csv(DATA_PATH).drop_duplicates().copy()
    required = ["CompanyName", "Industry", "Year", *ESG_COLUMNS]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"Dataset is missing columns: {', '.join(missing)}")

    numeric_columns = data.select_dtypes(include=np.number).columns
    for column in numeric_columns:
        median = data[column].median()
        if pd.notna(median):
            data[column] = data[column].fillna(median)

    # The project proposal specifies weights of 40% Environmental, 30% Social,
    # and 30% Governance. The three pillar scores are already on a 0-100 scale.
    data["Calculated_ESG_Score"] = (
        data["ESG_Environmental"] * 0.4
        + data["ESG_Social"] * 0.3
        + data["ESG_Governance"] * 0.3
    ).clip(0, 100)
    data["ESG_Category"] = data["Calculated_ESG_Score"].apply(score_category)
    data["ESG_Risk"] = data["Calculated_ESG_Score"].apply(risk_category)
    return data


def score_category(score):
    if pd.isna(score):
        return "Low"
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def risk_category(score):
    """Risk bands from the project proposal: >=80 low, >=60 medium, else high."""
    if score >= 80:
        return "Low Risk"
    if score >= 60:
        return "Medium Risk"
    return "High Risk"


df = load_dataset()


def records_json(frame):
    """Make Pandas records safe to return as JSON (missing values become null)."""
    safe_frame = frame.astype(object).where(pd.notna(frame), None)
    return safe_frame.to_dict(orient="records")


def latest_company_records(frame=None):
    """Return one latest-year row per company for fair company-level comparisons."""
    source = df if frame is None else frame
    return source.sort_values("Year").groupby("CompanyName", as_index=False).tail(1).copy()


# ML labels are derived from the weighted ESG score because the provided dataset
# has no independent real-world ESG-risk label. This is a proxy demonstration,
# not proof that the model predicts actual future risk.
ml_data = df.dropna(subset=ML_FEATURES + ["Calculated_ESG_Score"]).copy()
ml_data["Risk_Label"] = ml_data["Calculated_ESG_Score"].apply(risk_category)
X = ml_data[ML_FEATURES]
y = ml_data["Risk_Label"]
groups = ml_data["CompanyID"] if "CompanyID" in ml_data.columns else ml_data["CompanyName"]
splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_indices, test_indices = next(splitter.split(X, y, groups))
X_train, X_test = X.iloc[train_indices], X.iloc[test_indices]
y_train, y_test = y.iloc[train_indices], y.iloc[test_indices]

models = {
    "Logistic Regression": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced")),
    "Decision Tree": make_pipeline(SimpleImputer(strategy="median"), DecisionTreeClassifier(max_depth=6, class_weight="balanced", random_state=42)),
    "Random Forest": make_pipeline(SimpleImputer(strategy="median"), RandomForestClassifier(n_estimators=120, max_depth=10, class_weight="balanced", random_state=42, n_jobs=-1)),
}
model_results = []
for model_name, model in models.items():
    model.fit(X_train, y_train)
    predicted = model.predict(X_test)
    model_results.append({
        "model": model_name,
        "accuracy": round(float(accuracy_score(y_test, predicted)), 3),
        "precision": round(float(precision_score(y_test, predicted, average="weighted", zero_division=0)), 3),
        "recall": round(float(recall_score(y_test, predicted, average="weighted", zero_division=0)), 3),
        "f1_score": round(float(f1_score(y_test, predicted, average="weighted", zero_division=0)), 3),
    })
best_result = max(model_results, key=lambda result: result["f1_score"])
best_model = models[best_result["model"]]
class_names = list(best_model.classes_)
confusion = confusion_matrix(y_test, best_model.predict(X_test), labels=class_names).tolist()


@app.route("/")
def home_dashboard():
    return render_template("index.html")


@app.route("/api/summary")
def summary():
    return jsonify({
        "total_records": int(len(df)),
        "total_companies": int(df["CompanyName"].nunique()),
        "average_esg_score": round(float(df["Calculated_ESG_Score"].mean()), 2),
        "high_performers": int((df["ESG_Category"] == "High").sum()),
        "medium_performers": int((df["ESG_Category"] == "Medium").sum()),
        "low_performers": int((df["ESG_Category"] == "Low").sum()),
    })


@app.route("/api/top-companies")
def top_companies():
    columns = ["CompanyName", "Industry", "Year", "Calculated_ESG_Score", "ESG_Category"]
    top = latest_company_records().sort_values("Calculated_ESG_Score", ascending=False).head(10)
    return jsonify(records_json(top[columns]))


@app.route("/api/ranking")
def ranking():
    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), 100)
    except ValueError:
        return jsonify({"error": "limit must be a number."}), 400
    columns = ["CompanyName", "Industry", "Year", *ESG_COLUMNS, "Calculated_ESG_Score", "ESG_Risk"]
    ranked = latest_company_records().sort_values("Calculated_ESG_Score", ascending=False).head(limit)
    ranked.insert(0, "Rank", range(1, len(ranked) + 1))
    return jsonify(records_json(ranked[["Rank", *columns]]))


@app.route("/api/companies")
def companies():
    return jsonify(sorted(df["CompanyName"].dropna().astype(str).unique().tolist()))


@app.route("/api/industries")
def industries():
    return jsonify(sorted(df["Industry"].dropna().astype(str).unique().tolist()))


@app.route("/api/industry")
def industry_analysis():
    industry = request.args.get("name", "").strip()
    if not industry:
        return jsonify({"error": "Please provide an industry name."}), 400
    result = df[df["Industry"].astype(str).str.casefold() == industry.casefold()]
    if result.empty:
        return jsonify({"error": "Industry not found."}), 404
    return jsonify({
        "industry": industry,
        "records": int(len(result)),
        "average_esg_score": round(float(result["Calculated_ESG_Score"].mean()), 2),
        "average_revenue": round(float(result["Revenue"].mean()), 2),
    })


@app.route("/api/company")
def company_analysis():
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "Please provide a company name."}), 400
    result = df[df["CompanyName"].astype(str).str.casefold() == name.casefold()].sort_values("Year")
    if result.empty:
        return jsonify({"error": "Company not found."}), 404
    columns = ["CompanyName", "Year", "Revenue", "ProfitMargin", *ESG_COLUMNS, "Calculated_ESG_Score", "ESG_Category", "ESG_Risk"]
    return jsonify(records_json(result[[column for column in columns if column in result.columns]]))


@app.route("/api/compare")
def compare_companies():
    names = [name.strip() for name in request.args.get("companies", "").split(",") if name.strip()]
    names = list(dict.fromkeys(names))
    if not 2 <= len(names) <= 5:
        return jsonify({"error": "Select between 2 and 5 different companies."}), 400
    latest = latest_company_records()
    found = latest[latest["CompanyName"].isin(names)].copy()
    missing = [name for name in names if name not in set(found["CompanyName"])]
    if missing:
        return jsonify({"error": "Company not found: " + ", ".join(missing)}), 404
    columns = ["CompanyName", "Industry", "Year", *ESG_COLUMNS, "Calculated_ESG_Score", "ESG_Risk", "Revenue", "ProfitMargin"]
    return jsonify(records_json(found[columns]))


@app.route("/api/portfolio", methods=["POST"])
def portfolio_analysis():
    body = request.get_json(silent=True) or {}
    holdings = body.get("holdings", [])
    if not isinstance(holdings, list) or not holdings:
        return jsonify({"error": "Add at least one company and its investment weight."}), 400
    latest = latest_company_records().set_index("CompanyName")
    clean_holdings = []
    for item in holdings:
        company = str(item.get("company", "")).strip()
        try:
            weight = float(item.get("weight", 0))
        except (TypeError, ValueError):
            return jsonify({"error": f"Invalid weight for {company or 'a company'}."}), 400
        if company not in latest.index:
            return jsonify({"error": f"Company not found: {company}"}), 404
        if weight < 0:
            return jsonify({"error": "Weights cannot be negative."}), 400
        if weight > 0:
            clean_holdings.append({
                "company": company,
                "weight": weight,
                "esg_score": float(latest.loc[company, "Calculated_ESG_Score"]),
                "risk": str(latest.loc[company, "ESG_Risk"]),
            })
    total_weight = sum(item["weight"] for item in clean_holdings)
    if not clean_holdings or abs(total_weight - 100) > 0.01:
        return jsonify({"error": "Investment weights must add up to 100%."}), 400
    portfolio_score = sum(item["weight"] / 100 * item["esg_score"] for item in clean_holdings)
    return jsonify({
        "portfolio_esg_score": round(portfolio_score, 2),
        "total_weight": round(total_weight, 2),
        "holdings": clean_holdings,
        "assessment": "Strong ESG profile" if portfolio_score >= 80 else "Moderate ESG profile" if portfolio_score >= 60 else "Requires further ESG review",
    })


@app.route("/api/ml/metrics")
def ml_metrics():
    return jsonify({
        "target_note": "Risk classes are derived from the project's weighted ESG score because the CSV has no independent risk labels. This is a proxy classification exercise, not verified future-risk prediction.",
        "best_model": best_result["model"],
        "models": model_results,
        "class_names": class_names,
        "confusion_matrix": confusion,
        "features": ML_FEATURES,
    })


@app.route("/api/ml/predict")
def ml_predict():
    company = request.args.get("company", "").strip()
    if not company:
        return jsonify({"error": "Provide a company name."}), 400
    company_rows = latest_company_records()
    match = company_rows[company_rows["CompanyName"].astype(str).str.casefold() == company.casefold()]
    if match.empty:
        return jsonify({"error": "Company not found."}), 404
    row = match.iloc[0]
    sample = pd.DataFrame([{feature: row.get(feature, np.nan) for feature in ML_FEATURES}], columns=ML_FEATURES)
    predicted_risk = str(best_model.predict(sample)[0])
    probabilities = best_model.predict_proba(sample)[0]
    probability_by_class = {str(label): round(float(prob), 3) for label, prob in zip(best_model.classes_, probabilities)}

    # SHAP gives a local explanation for the selected company's prediction.
    # If SHAP is unavailable, the API returns the Random Forest's global feature importance.
    explanation = []
    explanation_method = "Random Forest feature importance"
    try:
        import shap
        rf_pipeline = models["Random Forest"]
        rf_model = rf_pipeline.named_steps["randomforestclassifier"]
        imputer = rf_pipeline.named_steps["simpleimputer"]
        sample_values = imputer.transform(sample)
        explainer = shap.TreeExplainer(rf_model)
        shap_values = explainer(sample_values)
        values = np.asarray(shap_values.values)
        predicted_index = list(rf_model.classes_).index(predicted_risk)
        if values.ndim == 3:
            contributions = values[0, :, predicted_index]
        elif values.ndim == 2:
            contributions = values[0]
        else:
            contributions = np.zeros(len(ML_FEATURES))
        explanation = [{"feature": feature, "value": round(float(row.get(feature, 0)), 2), "impact": round(float(impact), 4)} for feature, impact in zip(ML_FEATURES, contributions)]
        explanation.sort(key=lambda item: abs(item["impact"]), reverse=True)
        explanation_method = "SHAP (local feature contribution)"
    except Exception:
        rf_model = models["Random Forest"].named_steps["randomforestclassifier"]
        explanation = [{"feature": feature, "value": round(float(row.get(feature, 0)), 2), "importance": round(float(importance), 4)} for feature, importance in zip(ML_FEATURES, rf_model.feature_importances_)]
        explanation.sort(key=lambda item: item.get("importance", 0), reverse=True)

    return jsonify({
        "company": str(row["CompanyName"]),
        "year": int(row["Year"]),
        "predicted_risk": predicted_risk,
        "probabilities": probability_by_class,
        "model": best_result["model"],
        "explanation_method": explanation_method,
        "explanation": explanation[:5],
        "proxy_label": str(row["ESG_Risk"]),
        "warning": "The training target is derived from ESG-score bands, not an independently verified risk label. Treat this as a classroom ML demonstration.",
    })


@app.route("/api/records")
def all_records():
    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = min(max(int(request.args.get("per_page", 25)), 1), 100)
    except ValueError:
        return jsonify({"error": "page and per_page must be integers."}), 400
    search = request.args.get("search", "").strip().casefold()
    result = df
    if search:
        region = result.get("Region", pd.Series("", index=result.index))
        mask = (
            result["CompanyName"].astype(str).str.casefold().str.contains(search, na=False)
            | result["Industry"].astype(str).str.casefold().str.contains(search, na=False)
            | region.astype(str).str.casefold().str.contains(search, na=False)
        )
        result = result[mask]
    total = len(result)
    start = (page - 1) * per_page
    columns = ["CompanyName", "Industry", "Region", "Year", "Revenue", "ProfitMargin", "Calculated_ESG_Score", "ESG_Category"]
    columns = [column for column in columns if column in result.columns]
    return jsonify({"page": page, "per_page": per_page, "total": int(total), "records": records_json(result.iloc[start:start + per_page][columns])})


@app.route("/api/esg-distribution")
def esg_distribution():
    counts = df["ESG_Category"].value_counts()
    return jsonify({category: int(counts.get(category, 0)) for category in ["High", "Medium", "Low"]})


@app.route("/api/report.csv")
def download_report():
    """Download a simple company-level CSV summary for the project report."""
    columns = ["CompanyName", "Industry", "Region", "Year", *ESG_COLUMNS, "Calculated_ESG_Score", "ESG_Risk", "Revenue", "ProfitMargin"]
    report = latest_company_records()[[column for column in columns if column in df.columns or column in ["Calculated_ESG_Score", "ESG_Risk"]]].sort_values("Calculated_ESG_Score", ascending=False)
    output = BytesIO(report.to_csv(index=False).encode("utf-8-sig"))
    return send_file(output, mimetype="text/csv", as_attachment=True, download_name="esg_company_summary.csv")


if __name__ == "__main__":
    print("ESG Investment Analytics Platform")
    print(f"Loaded {len(df):,} records for {df['CompanyName'].nunique():,} companies.")
    print(f"Best demo classifier: {best_result['model']} (F1: {best_result['f1_score']})")
    print("Open http://127.0.0.1:5000 in your browser.")
    app.run(debug=True)
