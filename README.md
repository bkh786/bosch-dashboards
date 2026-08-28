# Bosch Visual Merchandising — Program Performance Dashboard

A real-time, interactive program performance dashboard for the **Bosch Visual Merchandising Program**, built by Channelplay. The dashboard parses live data from the master SharePoint workbook (`vm_rank_report`), displaying key performance indicators (KPIs), geographic and managerial coverage analytics, executive leaderboards, and a complete VM rank report.

---

## 🚀 Live Features & Capabilities

### 1. Corporate Brand Header & Pinned Navigation
- **Navigation Tabs**: Seamless navigation between *Program Performance Dashboard*, *QC Performance Dashboard*, and *Training Performance Dashboard*.
- **Branding**: Bosch brand logo and centered Channelplay pill badge.
- **Controls**: 
  - `Download Report`: 1-click download of the raw master Excel report directly from SharePoint.
  - `Live data connected`: Pulsing indicator button that triggers instantaneous real-time sync.
  - `Reset filters`: Clears all filters back to full program view.
  - `☀️/🌙 Theme Toggle`: Dynamic switching between Dark mode (default) and Light mode.
- **Live Status Banner**: Displays sheet details (`vm_rank_report`), live sync timestamp, total visits count, target POSM status, and total active VMs count.

---

### 2. Cascading Real-Time Filters
- **Region**: Filter by West, South 1, North, East, South 2.
- **State**: Filter by individual states (Gujarat, Maharashtra, Karnataka, Telangana, Tamil Nadu, Kerala, Punjab, Delhi, Rajasthan, Uttar Pradesh, West Bengal, Bihar, Andhra Pradesh).
- **AOM Name**: Filter by Area Operations Manager (Danish Khan, Irfan Ali, Pratik Kumar Pandey, Najeeb Hydrose).
- **VM Name**: Filter by individual Visual Merchandiser.
- *All 15 KPI tiles, charts, and tables update instantaneously upon filter selection.*

---

### 3. 15 Customized KPI Tiles

| KPI Metric | Description / Primary Value | Second-Line Breakdown |
| :--- | :--- | :--- |
| **Overall Coverage %** | Program-wide coverage achievement % | Target, Achievement, Pending count |
| **Cat A 1st Coverage %** | Category A 1st visit coverage % | Cat A Target, Achievement, Pending count |
| **Cat A 2nd Visit %** | Category A 2nd visit achievement % | Cat A Target, Achievement, Pending count |
| **Cat B Coverage %** | Category B coverage achievement % | Cat B Target, Achievement, Pending count |
| **Total Visit Achievement** | Total visit achievement % | Visit Target, Achieved, Pending count |
| **Productive Visit %** | Quality visit % (Non-unproductive) | Productive Visits count, Total Visits count |
| **Total Display Reported** | Display availability across visits | Status: **TBC** (Avg. display per visit: TBC) |
| **Total POSM Deployed** | POSM materials deployed | Status: **TBC** (POSM deployment per visit: TBC) |
| **Man-Days Achievement %** | Actual working man-days achievement | Target Man-Days, Achieved Man-Days |
| **Average Productivity** | Average visits per man-day | Benchmark target: ~4.0 visits/day |
| **BT Coverage %** | Base Town outlet coverage % | Target, Achieved, Pending count |
| **UPC Coverage %** | UPC outlet coverage % | Target, Achieved, Pending count |
| **Time Spent in Market** | Avg. market hours per working day | Converted from day fraction to `Hh Mm` |
| **Working Hrs.** | Avg. total shift hours per working day | Converted from day fraction to `Hh Mm` |
| **First Visit Time Adherence** | Adherence to first store check-in | Benchmark Target: **11:30 AM** |

---

### 4. Interactive Column Charts
- **State-wise Overall Coverage**: Dynamic bar chart showing Coverage % across all states with color-coded performance thresholds (Green ≥90%, Blue ≥80%, Amber ≥70%, Red <70%) and rich tooltips.
- **Region-wise & AOM-wise Coverage**: Grouped comparative column chart displaying coverage rates by Region and Area Operations Manager.

---

### 5. Performance Tables
- **Top 5 & Bottom 5 Performers (Side-by-Side)**:
  - Top 5 VM leaderboard with Gold, Silver, and Bronze rank medals.
  - Bottom 5 VM list highlighting focus areas requiring operational support.
- **AOM Performance based on VM Rank**:
  - Executive table populated from columns 57–65 of `vm_rank_report`: Rank, AOM Name, Base Town, Coverage %, Cat A Coverage, Achi Mandays %, Productivity, First Visit Time Adherence (11:30 AM), and Final Achievement.
- **Complete Rank Report**:
  - Full sortable, searchable, and paginated table of all 34 Visual Merchandisers.
  - Search by name, code, AOM, state, region.
  - Export to CSV capability.

---

## 🔍 Quality Check (QC) Performance Dashboard (`qc.html`)

A dedicated quality audit analytics dashboard parsing live data from the master SharePoint workbook (`QC Tracker` sheet).

### Key Features:
- **12 Evaluated Parameters**:
  - *Display Audit*: Ref Section, WM Section, Dishwasher Section, Chimney Section, Inside Snap (360 Images).
  - *Visibility Audit*: External Visibility, Internal Visibility, Promoter Activity.
  - *Campaign Audit*: Images taken correctly (Before & After), POSM Deployment (Guideline Adherence), Correct POSM Remarks Captured, POSM Condition (Damaged POSM identified).
- **Executive KPIs**: Total Audits, Overall QC Score % (Target benchmark ≥ 80%), Display Audit Score %, Campaign & Visibility Score %, Unique Users Audited, and Rejection Cases.
- **Dual-Axis Charts**:
  - AOM-wise QC Score % (Bar) and Audit Count (Line).
  - Week-wise QC Done (Past 8 Weeks volume and unique users audited).
  - Parameter-wise Compliance for Display and Campaign/Visibility.
  - 3 Score Trendline Cards (Overall, Display, Campaign trajectories).
- **Leaderboards & Coaching Insights**:
  - Side-by-side Top 5 & Bottom 5 VM rankings with medal badges.
  - Management Insights (Highlights & Lowlights directly synthesized from Mistakes Reported and AOM Remarks).
- **Audit Records Explorer**:
  - Searchable rejection cases table with parameter pass/fail badges, color-coded mistake/AOM tags, and CSV export.

---

## 🔄 Real-time Update Architecture (Zero File Upload)

The dashboards do **not** use or require any file upload mechanism. Instead, they employ a 3-tier real-time sync architecture:
1. **Tier 1 — Embedded Dataset**: Initial snapshots are embedded directly inside `index.html` and `qc.html` in `<script id="sample-data">` tags, ensuring 0 ms instantaneous load time with zero lag.
2. **Tier 2 — Client-Side Live Sync**: On page load (and whenever clicking `Live data connected`, or on the automatic 5-minute timer), the browser queries the SharePoint direct export URLs via CORS proxies, re-parses the Excel stream using SheetJS, and refreshes dashboard states.
3. **Tier 3 — Automated GitHub Action**: A scheduled workflow (`.github/workflows/sync_sharepoint_data.yml`) runs every 2 hours using `sync_datasets.py` to pull the latest workbooks from SharePoint, update `index.html`, `qc.html`, `data.json`, and `data_qc.json`, and push commits to `main`.

---

## 💻 Local Development

To run the dashboards locally:

```bash
# Start local HTTP server
python3 -m http.server 8080

# Open Program Performance: http://localhost:8080/index.html
# Open QC Performance:      http://localhost:8080/qc.html
```

To manually synchronize live data using Python:

```bash
python3 sync_datasets.py
```

