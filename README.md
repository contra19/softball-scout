# Softball Scout Stats

A simple web app for managing softball scouting statistics.

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the app:
```bash
streamlit run app.py
```

3. Open http://localhost:8501 in your browser

## Usage

### Create New Sheet
1. Select "Create New Sheet" from sidebar
2. Enter team name and location
3. Upload game CSVs to add data

### Update Existing Sheet
1. Select "Update Existing Sheet" from sidebar
2. Upload your existing .xlsx file
3. Select a team or add a new one
4. Upload game CSVs to add data
5. Download the updated file

## CSV Format

Your game CSV should have these columns:
- `Player` - Player name
- `AB` - At bats
- `R` - Runs
- `H` - Hits
- `RBI` - Runs batted in
- `BB` - Walks (optional)
- `SO` - Strikeouts

The app will try to match columns by name (case-insensitive).

## Test Data

Sample CSV files are in the `test-data/` folder for testing.
