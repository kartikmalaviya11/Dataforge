import os
import sys
import time
import shutil
import zipfile
import hashlib
import json
import subprocess
import urllib.request
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright

TEST_PORT = 8529
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"
ACCEPTANCE_DATA_DIR = Path("tests/acceptance_data")

@pytest.fixture(scope="module")
def browser_app():
    """Starts the Streamlit server and launches a Playwright Chromium session."""
    ACCEPTANCE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    customers_file = (ACCEPTANCE_DATA_DIR / "customers.csv").resolve()
    orders_file = (ACCEPTANCE_DATA_DIR / "orders.csv").resolve()
    if not customers_file.exists():
        customers_file.write_text(
            "customer_id,customer_name,email,region\n"
            "1,Alice Smith,alice@example.com,North\n"
            "2,Bob Jones,bob@example.com,South\n"
            "3,Charlie Brown,charlie@example.com,East\n"
            "4,Diana Prince,diana@example.com,West\n"
            "5,Evan Wright,evan@example.com,North\n"
            "6, Frank Castle ,frank@example.com,\n"
        )
    if not orders_file.exists():
        orders_file.write_text(
            "order_id,customer_id,order_date,revenue,status,review_score\n"
            "101,1,2023-01-15,150.00,Delivered,5\n"
            "102,2,2023-01-18,220.50,Delivered,4\n"
            "103,1,2023-02-01,90.00,Returned,1\n"
            "104,3,2023-02-14,310.00,Delivered,5\n"
            "105,4,2023-03-05,45.00,Cancelled,2\n"
            "106,5,2023-03-20,180.00,Delivered,4\n"
            "107,2,2023-04-02,75.00,Returned,1\n"
            "108,3,2023-04-10,400.00,Delivered,5\n"
        )

    Path("scratch").mkdir(parents=True, exist_ok=True)
    server_log = open("scratch/browser_pytest_server.log", "w", encoding="utf-8")
    cmd = [
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", str(TEST_PORT),
        "--server.headless", "true",
        "--server.fileWatcherType", "none",
        "--browser.gatherUsageStats", "false"
    ]
    proc = subprocess.Popen(cmd, stdout=server_log, stderr=subprocess.STDOUT)

    # Wait for server readiness
    server_ready = False
    for _ in range(45):
        try:
            resp = urllib.request.urlopen(BASE_URL, timeout=1)
            if resp.status == 200:
                server_ready = True
                break
        except Exception:
            time.sleep(1)

    if not server_ready:
        proc.kill()
        server_log.close()
        pytest.fail(f"Streamlit server failed to start on {BASE_URL}")

    # Launch Playwright Chromium
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1366, "height": 900})
    page = context.new_page()

    state = {
        "proc": proc,
        "server_log": server_log,
        "playwright": playwright,
        "browser": browser,
        "context": context,
        "page": page,
        "customers_file": customers_file,
        "orders_file": orders_file,
        "workspace_root": None
    }

    yield state

    # Teardown
    try:
        browser.close()
    except Exception:
        pass
    try:
        playwright.stop()
    except Exception:
        pass
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    try:
        server_log.close()
    except Exception:
        pass

def nav_to(page, page_name: str):
    """Helper to click sidebar navigation button reliably."""
    sidebar = page.locator('section[data-testid="stSidebar"]')
    btn = sidebar.locator(f'button:has-text("{page_name}")')
    btn.wait_for(state="visible", timeout=15000)
    btn.click()
    page.wait_for_timeout(1000)

class TestDataForgeBrowserAcceptance:

    def test_01_empty_states_and_initial_navigation(self, browser_app):
        """Workflow 0: Verify initial page, branding, and locked navigation."""
        page = browser_app["page"]
        page.goto(BASE_URL)
        page.wait_for_selector('h1:has-text("DATAFORGE")', timeout=30000)
        assert page.locator('h1:has-text("DATAFORGE")').is_visible()
        assert page.locator('text=Import your data').is_visible()

        # Check navigation before project load
        sidebar = page.locator('section[data-testid="stSidebar"]')
        assert sidebar.locator('text=Data Import').is_visible()
        assert sidebar.locator('text=Overview').is_visible()

    def test_02_create_project_and_import_dataset(self, browser_app):
        """Workflow 1: Upload dataset files, verify SHA-256 integrity and overview transition."""
        page = browser_app["page"]
        cust_file = browser_app["customers_file"]
        ord_file = browser_app["orders_file"]

        # Calculate original SHA-256 hashes
        h_cust_orig = hashlib.sha256(cust_file.read_bytes()).hexdigest()
        h_ord_orig = hashlib.sha256(ord_file.read_bytes()).hexdigest()
        browser_app["h_cust_orig"] = h_cust_orig
        browser_app["h_ord_orig"] = h_ord_orig

        # Upload files
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files([str(cust_file), str(ord_file)])

        # Wait for Selected Files table and Ready status
        page.wait_for_selector('text=Selected Files', timeout=25000)
        page.wait_for_selector('text=Ready', timeout=25000)
        assert page.locator('text=Ready').count() >= 2

        # Start Analysis
        start_btn = page.locator('button:has-text("Start Analysis")')
        assert start_btn.is_visible()
        start_btn.click()

        # Wait for Overview page transition
        page.wait_for_selector('h3:has-text("Project Overview")', timeout=35000)
        assert page.locator('h3:has-text("Project Overview")').is_visible()

        # Verify raw files stored in project workspace match original SHA-256
        workspaces_dir = Path(".dataforge_workspaces")
        assert workspaces_dir.exists()
        latest_ws = sorted(workspaces_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[0]
        browser_app["workspace_root"] = latest_ws

        ws_cust = latest_ws / "customers.csv"
        ws_ord = latest_ws / "orders.csv"
        assert ws_cust.exists()
        assert ws_ord.exists()
        assert hashlib.sha256(ws_cust.read_bytes()).hexdigest() == h_cust_orig
        assert hashlib.sha256(ws_ord.read_bytes()).hexdigest() == h_ord_orig

    def test_03_data_profiling_and_quality_scan(self, browser_app):
        """Workflow 2: Run Data Quality scan, semantic type detection, and view issues."""
        page = browser_app["page"]
        nav_to(page, "Data Quality")
        page.wait_for_selector('h2:has-text("Data Quality Scan")', timeout=15000)

        # Click Scan Table
        scan_btn = page.locator('button:has-text("Scan Table")')
        scan_btn.wait_for(state="visible", timeout=15000)
        scan_btn.click()

        page.wait_for_selector('text=Scan completed', timeout=30000)
        assert page.locator('text=Scan completed').is_visible()

        # Navigate to Issues
        nav_to(page, "Issues")
        page.wait_for_selector('h2:has-text("Issues")', timeout=15000)
        page.wait_for_selector('text=Found', timeout=15000)
        assert page.locator('text=Found').is_visible()

    def test_04_propose_repairs_preview_and_immutability(self, browser_app):
        """Workflow 3: Propose repair, approve safe fix, and verify raw source unchanged."""
        page = browser_app["page"]
        nav_to(page, "Cleaning")
        page.wait_for_selector('h2:has-text("Data Cleaning & Repair")', timeout=15000)

        # Approve Safe Fixes
        page.wait_for_selector('text=Generated', timeout=15000)
        approve_btn = page.locator('button:has-text("Approve Safe Fixes")')
        if approve_btn.is_visible():
            approve_btn.click()
            page.wait_for_selector('text=Repairs applied', timeout=25000)
            assert page.locator('text=Repairs applied').is_visible()

        # Verify RAW file immutability (customers.csv and orders.csv byte-for-byte identical to original)
        ws_root = browser_app["workspace_root"]
        ws_cust = ws_root / "customers.csv"
        ws_ord = ws_root / "orders.csv"
        assert hashlib.sha256(ws_cust.read_bytes()).hexdigest() == browser_app["h_cust_orig"]
        assert hashlib.sha256(ws_ord.read_bytes()).hexdigest() == browser_app["h_ord_orig"]

    def test_05_custom_pattern_validation(self, browser_app):
        """Workflow 4: Custom pattern validation with invalid regex (error handling) and valid regex."""
        page = browser_app["page"]
        nav_to(page, "Validation")
        page.wait_for_selector('h2:has-text("Validation Results & Custom Patterns")', timeout=15000)

        # Switch to Custom Pattern Validation tab
        pat_tab = page.get_by_text("Custom Pattern Validation", exact=True)
        pat_tab.wait_for(state="visible", timeout=15000)
        pat_tab.click()
        page.wait_for_timeout(1000)

        pat_input = page.locator('div[data-testid="stTextInput"] input').last
        validate_btn = page.locator('button:has-text("Validate Pattern")')

        # Test Invalid Regex
        pat_input.fill("[invalid(")
        validate_btn.click()
        page.wait_for_selector('div[data-testid="stAlert"]', timeout=10000)
        alert_text = page.locator('div[data-testid="stAlert"]').inner_text()
        assert any(term in alert_text.lower() for term in ["unterminated", "pattern", "error", "regex", "missing"])

        # Test Valid Regex
        pat_input.fill("^[A-Za-z]+$")
        validate_btn.click()
        page.wait_for_selector('text=Regex applied successfully', timeout=15000)
        assert page.locator('text=Regex applied successfully').is_visible()
        assert page.locator('text=Matches:').first.is_visible()

    def test_06_relationships_and_erd(self, browser_app):
        """Workflow 5: Detect cross-table relationships and verify ERD output."""
        page = browser_app["page"]
        nav_to(page, "Relationships")
        page.wait_for_selector('h2:has-text("Relationships")', timeout=15000)

        detect_btn = page.locator('button:has-text("Detect Relationships")')
        detect_btn.click()

        # Wait for candidates table and ERD diagram
        page.wait_for_selector('h3:has-text("Entity Relationship Diagram")', timeout=30000)
        assert page.locator('h3:has-text("Entity Relationship Diagram")').is_visible()
        page.wait_for_selector('div[data-testid="stGraphvizChart"], svg', timeout=15000)
        assert page.locator('div[data-testid="stDataFrame"]').first.is_visible()

    def test_07_sql_and_pandas_analysis(self, browser_app):
        """Workflow 6: Run SQL analytical queries and Pandas describe summary."""
        page = browser_app["page"]
        nav_to(page, "SQL Workspace")
        page.wait_for_selector('h2:has-text("SQL Workspace")', timeout=15000)

        # Enter and run analytical query
        sql_input = page.locator('textarea').first
        sql_input.fill("SELECT status, count(*) as cnt, sum(revenue) as total_rev FROM orders GROUP BY status ORDER BY cnt DESC;")
        sql_input.press("Control+Enter")
        page.wait_for_timeout(1000)

        run_sql_btn = page.locator('button:has-text("Run Query")')
        run_sql_btn.click()

        # Wait for query result dataframe
        page.wait_for_selector('div[data-testid="stDataFrame"]', timeout=20000)
        assert page.locator('div[data-testid="stDataFrame"]').is_visible()

        # Navigate to Pandas Analysis
        nav_to(page, "Pandas Analysis")
        page.wait_for_selector('h2:has-text("Pandas Analysis")', timeout=15000)

        describe_btn = page.locator('button:has-text("Describe")')
        describe_btn.click()
        page.wait_for_selector('div[data-testid="stDataFrame"]', timeout=20000)
        assert page.locator('div[data-testid="stDataFrame"]').is_visible()

    def test_08_kpi_center_and_snapshots(self, browser_app):
        """Workflow 7: Generate KPIs, log snapshots, and execute snapshot comparison."""
        page = browser_app["page"]
        nav_to(page, "KPI Center")
        page.wait_for_selector('h2:has-text("KPI Center")', timeout=15000)

        # Generate KPIs
        gen_kpi_btn = page.locator('button:has-text("Generate KPIs")')
        gen_kpi_btn.click()
        page.wait_for_selector('text=KPIs generated', timeout=25000)
        assert page.locator('text=KPIs generated').is_visible()

        # Create First Snapshot
        snap_btn = page.locator('button:has-text("Create Snapshot")')
        snap_btn.first.wait_for(state="visible", timeout=15000)
        snap_btn.first.click()
        page.wait_for_selector('text=Created', timeout=20000)
        assert page.locator('text=Created').is_visible()

        # Create Second Snapshot
        page.wait_for_timeout(1000)
        snap_btn.click()
        page.wait_for_timeout(1500)

        # Compare Snapshots section
        page.wait_for_selector('text=Compare Snapshots', timeout=15000)
        assert page.locator('text=Compare Snapshots').is_visible()
        page.wait_for_selector('div[data-testid="stJson"]', timeout=15000)
        json_text = page.locator('div[data-testid="stJson"]').inner_text()
        assert "snapshot_id_a" in json_text
        assert "snapshot_id_b" in json_text

    def test_09_business_questions_and_rca(self, browser_app):
        """Workflow 8: Business questions validation & RCA interactive filter execution."""
        page = browser_app["page"]
        nav_to(page, "Business Questions")
        page.wait_for_selector('h2:has-text("Business Questions")', timeout=15000)

        # Empty question input validation error
        save_q_btn = page.locator('button:has-text("Save Question")')
        save_q_btn.click()
        page.wait_for_selector('text=cannot be empty', timeout=10000)
        assert page.locator('text=cannot be empty').is_visible()

        # Valid question submission
        q_input = page.locator('input[aria-label="Question *"]').first
        q_input.fill("What drives revenue differences across order status?")
        save_q_btn.click()
        page.wait_for_selector('text=Question saved successfully', timeout=15000)
        assert page.locator('text=Question saved successfully').is_visible()

        # Generate schema suggestions
        sugg_btn = page.locator('button:has-text("Generate Schema Suggestions")')
        sugg_btn.click()
        page.wait_for_selector('text=question suggestion', timeout=25000)

        # Navigate to RCA
        nav_to(page, "RCA")
        page.wait_for_selector('h2:has-text("Root Cause Analysis")', timeout=15000)

        val_input = page.locator('input[aria-label="Condition Value"]').first
        val_input.fill("2")
        val_input.press("Enter")
        page.wait_for_timeout(1000)

        run_rca_btn = page.locator('button:has-text("Run RCA")')
        run_rca_btn.click()

        page.wait_for_selector('text=Root Cause Analysis completed successfully', timeout=30000)
        assert page.locator('text=Root Cause Analysis completed successfully').is_visible()
        assert page.locator('text=Overall Classification:').is_visible()

    def test_10_governance_lineage_and_dax(self, browser_app):
        """Workflow 9 & 10: Create assumption, generate docs, generate DAX, verify history & lineage."""
        page = browser_app["page"]

        # Assumptions
        nav_to(page, "Assumptions")
        page.wait_for_selector('h2:has-text("Assumptions Register")', timeout=15000)

        # Empty assumption validation
        reg_btn = page.locator('button:has-text("Register Assumption")')
        reg_btn.click()
        page.wait_for_selector('text=required', timeout=15000)
        assert page.locator('text=required').is_visible()

        # Fill valid assumption
        page.locator('input[aria-label="Assumption Title *"]').first.fill("Currency Base")
        page.locator('textarea[aria-label="Detailed Description *"]').first.fill("Transactions recorded in standard USD")
        reg_btn.click()
        page.wait_for_selector('text=registered successfully', timeout=15000)
        assert page.locator('text=registered successfully').is_visible()

        # Documentation
        nav_to(page, "Documentation")
        page.wait_for_selector('h2:has-text("Documentation Generator")', timeout=15000)
        gen_doc_btn = page.locator('button:has-text("Generate All Docs")')
        gen_doc_btn.click()
        page.wait_for_selector('text=Documentation Generated', timeout=25000)
        assert page.locator('text=Documentation Generated').is_visible()

        # Advanced DAX
        nav_to(page, "Advanced DAX")
        page.wait_for_selector('h2:has-text("DAX Generation")', timeout=15000)
        gen_dax_btn = page.locator('button:has-text("Generate DAX")')
        gen_dax_btn.click()
        page.wait_for_selector('text=Generated and saved', timeout=25000)
        assert page.locator('text=Generated and saved').is_visible()

        # Run History
        nav_to(page, "Run History")
        page.wait_for_selector('h2:has-text("Run History")', timeout=15000)
        assert page.locator('div[data-testid="stDataFrame"]').is_visible()

        # Dataset Versioning
        nav_to(page, "Dataset Versioning")
        page.wait_for_selector('h2:has-text("Dataset Versions")', timeout=15000)
        assert page.locator('div[data-testid="stDataFrame"]').is_visible()

        # Data Lineage
        nav_to(page, "Data Lineage")
        page.wait_for_selector('h2:has-text("Data Lineage")', timeout=15000)
        assert page.locator('div[data-testid="stDataFrame"], div[data-testid="stGraphvizChart"], svg').first.is_visible()
        assert page.locator('h2:has-text("Data Lineage")').is_visible()

    def test_11_project_export_package(self, browser_app):
        """Workflow 11: Generate real ZIP export and inspect package contents on disk."""
        page = browser_app["page"]
        nav_to(page, "Export Package")
        page.wait_for_selector('h2:has-text("Export Package")', timeout=15000)

        gen_pkg_btn = page.locator('button:has-text("Build Export Package")')
        gen_pkg_btn.click()

        page.wait_for_selector('text=Exported to', timeout=30000)
        assert page.locator('text=Exported to').is_visible()

        # Inspect generated zip in latest_ws / .dataforge / export
        latest_ws = browser_app["workspace_root"]
        export_pkg_dir = latest_ws / ".dataforge" / "export"
        assert export_pkg_dir.exists()
        zips = list(export_pkg_dir.glob("*.zip"))
        assert len(zips) >= 1
        target_zip = sorted(zips, key=lambda p: p.stat().st_mtime, reverse=True)[0]

        with zipfile.ZipFile(target_zip, "r") as z:
            names = z.namelist()
            assert "manifest.json" in names
            raw_files = [n for n in names if n.startswith("raw/") and n.endswith(".csv")]
            assert len(raw_files) >= 1
            meta_files = [n for n in names if n.startswith("metadata/") and n.endswith(".json")]
            assert len(meta_files) >= 1

            # Read manifest and verify hashes
            manifest_bytes = z.read("manifest.json")
            manifest_dict = json.loads(manifest_bytes.decode('utf-8'))
            for rel_path, expected_sha in manifest_dict.items():
                member_bytes = z.read(rel_path.replace('\\', '/'))
                assert hashlib.sha256(member_bytes).hexdigest() == expected_sha
