# Financial Aid Automation POC

Streamlit prototype for AI-assisted financial aid document intake at Morningside University.

## What it does

1. Upload a student's document packet (scanned PDFs)
2. OCR + AI classifies each document and extracts key fields
3. Flags missing or unclear items for advisor review
4. Generates a case summary and draft follow-up email

The app is workflow support only — it does not make aid decisions.

## Setup

1. Create and activate a virtual environment
2. `pip install -r requirements.txt`
3. Create a `.env` file with your OpenAI key:
   ```
   OPENAI_API_KEY=sk-...
   ```
4. `streamlit run app.py`

## Sample data

Pre-built student packages live in `sample_data/student_packages/`. Each folder contains 5 scanned PDFs and a `manifest.json` describing the scenario and expected AI catches. These can be loaded directly from the app's dropdown.

## Model configuration

Optional overrides via `.env`:
- `OPENAI_MODEL` — default model for all calls
- `OPENAI_OCR_MODEL` — model used for OCR
- `OPENAI_ANALYSIS_MODEL` — model used for classification and extraction
- `OPENAI_SUMMARY_MODEL` — model used for case summary
