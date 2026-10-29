# SproutLog — Home Gardening Recommendation System

## This version includes a recommendation engine
When you open **Recommendations →** for an observation, the app explains:
- possible reasons for yellow, brown, wilting, purple, or spotted leaves;
- what a wet or dry soil observation may mean;
- whether the entered watering routine may need reviewing;
- how the current height compares with the previous dated height measurement;
- how recorded sunlight hours and indoor/outdoor placement may affect the plant;
- practical next steps based on the recorded observations.

The recommendation engine is offline and rule-based. It is not a cloud AI model and does not require an API key. It offers possible causes rather than a definitive diagnosis. Species-specific needs differ, so enter the plant species and as many observations as you can.

## Run on Windows
1. Install Python 3.10+ from https://www.python.org/downloads/ (select “Add Python to PATH”).
2. Extract the ZIP.
3. Open Command Prompt in the extracted `home_gardening_ai` folder.
4. Run these commands:
   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   py app.py
   ```
5. Visit http://127.0.0.1:5000 in your browser.

## Run on macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Then open http://127.0.0.1:5000.

## Database
The app creates `garden.db` in this folder and upgrades an older database by adding the new observation fields. Back up this file to preserve records. Export all observations with the Export CSV button.

## Note about “AI”
This version implements a practical local recommendation system with rules. To use a generative AI model for open-ended plant-care chat or image analysis, you would need to add an AI provider/API key and related privacy and cost controls. No external AI calls are made by this version.
