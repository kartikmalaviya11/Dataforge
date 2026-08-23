# DATAFORGE 2.0: The Deterministic Analytics Pre-Processor

DATAFORGE 2.0 is a robust, deterministic data engineering and quality-assurance pipeline designed to bridge the gap between raw, messy datasets (CSV/Excel) and Business Intelligence platforms like Power BI. 

## Problem It Solves

Data professionals often receive "dirty" datasets containing trailing spaces, invalid dates, hidden duplicate rows, broken formulas, and ambiguous semantic types. Passing these directly into BI tools like Power BI or Tableau results in broken visuals, silent errors, and untrustworthy metrics.

DATAFORGE 2.0 solves this by strictly validating, classifying, proposing fixes for, and exporting clean datasets—without relying on unpredictable AI magic or black-box mutations. Everything is deterministic, previewable, explicit, and tracked.

---

## The DATAFORGE 2.0 Workflow

DATAFORGE 2.0 implements a strict, multi-step pipeline accessible via a dark-mode Streamlit dashboard:

1. **Upload**: Load raw `.csv` or `.xlsx` files into the system.
2. **Analyze**: Run a deep profile over columns to calculate sparseness, distinct counts, and patterns.
3. **Detect**: Systematically detect data quality issues (e.g., whitespace, exact duplicates, invalid numerics).
4. **Explain**: Generate plain-English reasons explaining *why* an issue was flagged.
5. **Classify**: Categorize every detected issue based on safety (see Issue Classifications below).
6. **Suggest**: Generate specific, row-level or column-level repair proposals.
7. **Preview**: Display all pending proposals in an interactive UI grid.
8. **Approve/Reject**: Let the user explicitly check/uncheck which fixes should be applied.
9. **Repair**: The Deterministic Repair Engine mutates the dataframe *only* where explicitly approved.
10. **Re-validate**: Run the quality engine a second time on the repaired data.
11. **Before/After**: Compare the initial dataset readiness against the post-repair readiness.
12. **Export**: Package the cleaned data alongside comprehensive metadata and change-logs into a ZIP archive.
13. **BI Ready**: Import the cleaned `.csv` or `.xlsx` and the auto-generated DAX/SQL into Power BI.

---

## Issue Classifications

Data mutation is inherently dangerous. DATAFORGE classifies every detected issue into one of three strict safety tiers:

* **`AUTO_FIXABLE`**: Deterministic fixes that are guaranteed to be safe (e.g., trimming trailing whitespace from strings, removing exact duplicate rows in flat files). These are checked for approval by default.
* **`REVIEW_REQUIRED`**: Fixes that involve assumptions or type coercion (e.g., assuming `$100` means `100.0`, or guessing a date format). These require explicit, manual user approval and are unchecked by default.
* **`UNSAFE_TO_FIX`**: Issues where no deterministic fix can be proposed without risk of data loss or structural damage (e.g., deleting rows in an Excel file that contains formulas or merged cells). These cannot be approved.

---

## Deterministic Repair Engine

The **Deterministic Repair Engine** is the execution core. It translates user approvals into concrete dataframe mutations.
* It operates *exclusively* on approved instructions. Unapproved or pending proposals are completely ignored.
* Operations are strictly scoped to the exact `row_index` of the approved instruction to prevent rogue column-sweeps.
* It maintains a comprehensive `ChangeRecord` mapping exactly what was mutated, why, and what the before/after values were.

---

## Preview & Approval Workflow

No silent mutations occur in DATAFORGE. Before any repairs are made, the `ProposalGenerator` generates a table of proposed fixes. The user is presented with a data grid where they can visually inspect the `Old Value` vs the `Proposed Value` and explicitly `Approve` or `Reject` the change. 

---

## Re-Validation and Before/After Comparison

After the Repair Engine executes the approved fixes, DATAFORGE immediately triggers a **Re-Validation** pass. The `RevalidationEngine` runs the full quality check again, comparing the "Before" snapshot against the "After" snapshot.

The UI displays clear metrics showing:
* Total issues resolved
* Remaining issues
* Overall Analytics Readiness Score improvement (e.g., `81.3%` -> `95.0%`).

---

## Analytics Export & ZIP Architecture

When the user clicks "Download Analytics Reports", DATAFORGE packages the entire context into a single ZIP file (`analytics_reports.zip`). 

Depending on the export format chosen, the ZIP includes:
* **Cleaned Dataset**: The repaired data ready for BI (`DATAFORGE_CLEANED.csv` or `.xlsx`).
* **Metadata & Summary**: `dataset_profile.csv`, `quality_summary.csv`.
* **Changes Made**: A strict audit log of every repair actually executed (`changes_made.csv`).
* **Needs Review**: A log of pending or rejected proposals (`needs_review.csv`).
* **KPIs & Measures**: `kpi_recommendations.csv`, `dax_measures.csv`.

---

## CSV vs Excel: Strict Safety Handling

DATAFORGE supports both CSV and Excel, but treats them distinctly:
* **CSV**: Handled as flat tabular data.
* **Excel (XLSX)**: Requires specialized inspection via the `ExcelQuality` engine. Before any analysis occurs, DATAFORGE checks the workbook for:
  * Formulas
  * Merged cells
  * Hidden rows/columns
  * Macros

### Formula and Merged-Cell Safety Limitations
If an Excel file contains formulas or merged cells, certain repairs (like `DUPLICATE_ROW` deletion) are strictly downgraded to `UNSAFE_TO_FIX`. Deleting a row in pandas does not update downstream Excel formulas, which would corrupt the workbook geometry. DATAFORGE strictly refuses to perform row-deletions on such files.

---

## KPIs, DAX, and DuckDB SQL Validation

Beyond data cleaning, DATAFORGE accelerates BI development:
* **KPI Recommendations**: Suggests relevant KPIs (e.g., `Total Sales`, `Average Profit`) based on detected semantic types.
* **DAX Generation**: Auto-generates Power BI-ready DAX measure formulas based on the KPI recommendations.
* **DuckDB SQL Validation**: Automatically generates and executes DuckDB SQL queries against the dataset in-memory to validate the logical correctness of the recommended KPIs before you ever open Power BI.

---

## Core Philosophy

* **No AI/API Dependency**: DATAFORGE is 100% local and deterministic. There are no black-box LLM calls mutating your data.
* **No Silent Mutation**: You always know exactly what changed and why.
* **No Guessing**: If a semantic type or rule is ambiguous, DATAFORGE falls back to `UNAVAILABLE` rather than generating fake or misleading insights.

---

## Testing & Validation

DATAFORGE is backed by a massive, rigorous test suite protecting against regressions.

**Current Testing Result:**
> **317 passed, 1 skipped**

The test suite covers:
* Ground-truth validation
* Excel integrity limits
* Repair Engine strict scoping
* Export structure integrity
* Safety state machine (AUTO_FIXABLE vs UNSAFE)

---

## Project Structure

```text
Dataforge/
├── app.py
├── pyproject.toml
├── requirements.txt
├── docs/
│   └── images/
├── src/
│   ├── ingestion.py
│   ├── profiler.py
│   ├── type_detector.py
│   ├── excel_quality.py
│   ├── quality_engine.py
│   ├── rules.py
│   ├── issue_manager.py
│   ├── proposal_generator.py
│   ├── repair_engine.py
│   ├── revalidation.py
│   ├── export_service.py
│   ├── scoring.py
│   ├── kpi_engine.py
│   ├── dax_generator.py
│   ├── sql_analyzer.py
│   ├── report_generator.py
│   └── main.py
└── tests/
    ├── test_app_workflow.py
    ├── test_excel_integrity.py
    ├── test_excel_quality.py
    ├── test_export.py
    ├── test_issue_manager.py
    ├── test_proposal.py
    ├── test_quality_engine.py
    ├── test_repair_engine.py
    ├── test_revalidation.py
    ├── test_rules.py
    ├── test_scoring.py
    ├── test_sql_analyzer.py
    ├── test_targeted_fix.py
    └── test_type_detector.py
```

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/kartikmalaviya11/Dataforge.git
cd Dataforge
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
```

### 3. Activate the environment

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
pip install -r requirements.txt
```

---

## Usage

Start the Streamlit application:

```powershell
streamlit run app.py
```

Then:
1. Upload a CSV or XLSX file.
2. Click **Analyze Dataset**.
3. Review the **Data Quality** tabs.
4. Go to **Suggested Fixes** to preview and approve `AUTO_FIXABLE` and `REVIEW_REQUIRED` repairs.
5. Click **Apply Approved Changes**.
6. Review the **Before/After Validation**.
7. Download the **Cleaned Dataset & Reports** ZIP file for Power BI.

---

## Author

**Kartik Malaviya**

BCA Student | Aspiring Data Analyst

Interested in:
* Data Analytics
* SQL
* Python
* Power BI
* Business Intelligence
* Data Quality
* Analytics Engineering

GitHub: [@kartikmalaviya11](https://github.com/kartikmalaviya11)

---

## License

This project is intended as a personal portfolio and learning project.
See the repository for licensing information before reuse or redistribution.
