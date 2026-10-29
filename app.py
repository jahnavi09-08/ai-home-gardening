from flask import Flask, render_template, request, redirect, url_for, flash, Response
import sqlite3, os, csv
from io import StringIO
from datetime import date

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "garden.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-development-key")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_name TEXT NOT NULL,
            plant_species TEXT DEFAULT '',
            observation_date TEXT NOT NULL,
            colour TEXT NOT NULL,
            height_cm REAL,
            location TEXT NOT NULL,
            sunlight_hours REAL,
            watering_frequency TEXT DEFAULT '',
            soil_condition TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )""")
        # Safely upgrade an existing database from the previous ZIP version.
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(observations)").fetchall()}
        for name, definition in [
            ("plant_species", "TEXT DEFAULT ''"),
            ("sunlight_hours", "REAL"),
            ("watering_frequency", "TEXT DEFAULT ''"),
            ("soil_condition", "TEXT DEFAULT ''")
        ]:
            if name not in existing:
                conn.execute(f"ALTER TABLE observations ADD COLUMN {name} {definition}")

def recommendations_for(obs, history):
    """Personalized, offline rule-based recommendations. These are possibilities, not diagnoses."""
    recs = []
    color = (obs.get("colour") or "").lower()
    location = (obs.get("location") or "").lower()
    notes = (obs.get("notes") or "").lower()
    soil = (obs.get("soil_condition") or "").lower()
    watering = (obs.get("watering_frequency") or "").lower()
    species = (obs.get("plant_species") or "").strip()
    sunlight = obs.get("sunlight_hours")
    height = obs.get("height_cm")

    def add(priority, title, reason, action):
        recs.append({"priority": priority, "title": title, "reason": reason, "action": action})

    # Colour-related possibilities
    if "yellow" in color or "pale" in color:
        add("Check first", "Yellow or pale leaves",
            "Yellowing can be linked to overwatering, poor drainage, insufficient light, or nutrient availability. The colour alone cannot identify the exact cause.",
            "Feel the soil before watering, confirm the pot has drainage holes, and check whether the plant receives the light recommended for its species. Note whether new or older leaves are yellowing.")
    elif "brown" in color or "dry" in color or "crispy" in color:
        add("Check first", "Brown or crispy leaves",
            "Dry leaf edges can occur with dry soil, irregular watering, strong sun, hot wind, or salt build-up. Brown spots can also have other causes.",
            "Check soil moisture 2–3 cm below the surface and look for a pattern: edges, tips, or isolated spots. Avoid leaving the pot in standing water.")
    elif "wilting" in color or "drooping" in color:
        add("Check first", "Wilting or drooping",
            "Both underwatering and overwatering can cause wilting; damaged roots can also prevent water uptake.",
            "Check the soil first. If it is dry, water thoroughly and let excess drain. If it is wet or smells sour, pause watering and inspect drainage and roots.")
    elif "spot" in color or "black" in color:
        add("Monitor closely", "Spots or dark areas",
            "Spots may be caused by leaf damage, sun scorch, pests, or disease. A text description is not enough to identify the cause reliably.",
            "Inspect both sides of leaves and stems. Avoid wetting foliage unnecessarily, improve airflow, and isolate the plant if spots spread quickly or pests are visible.")
    elif "purple" in color or "red" in color:
        add("Compare with normal growth", "Purple or reddish colour",
            "Some species naturally have red or purple leaves. If this is new, temperature, intense light, or nutrient availability may be involved.",
            "Compare with healthy examples of the same species and check recent temperature and light changes before changing fertiliser.")
    elif "green" in color or "healthy" in color or "normal" in color:
        add("Maintain", "Colour looks healthy",
            "A normal green appearance is encouraging, though leaf firmness and new growth also matter.",
            "Keep care steady, check the soil before watering, and record a new height measurement in 1–2 weeks.")

    # Soil and watering inputs make advice more specific.
    if "wet" in soil or "soggy" in soil or "waterlogged" in soil:
        add("High priority", "Soil is staying wet",
            "Persistently wet soil can reduce oxygen around roots and contribute to root damage, especially in pots without good drainage.",
            "Check drainage holes and empty any saucer. Let the top layer dry to the level appropriate for the species before watering again; do not follow a fixed daily schedule.")
    elif "dry" in soil:
        add("Check", "Soil feels dry",
            "Dry soil can contribute to wilting and dry leaf edges, but some plants prefer their soil to dry between waterings.",
            "Check the plant's species-specific needs. When watering is needed, water evenly until excess drains, then empty the saucer.")

    if "daily" in watering:
        add("Review routine", "Watering every day",
            "Daily watering is too frequent for many houseplants, though seedlings and some outdoor plants may need frequent checks in hot weather.",
            "Use soil moisture, pot size, weather, and plant species to decide when to water rather than watering by calendar alone.")
    elif "weekly" in watering or "once a week" in watering:
        add("Review routine", "Weekly watering routine",
            "A weekly schedule may be suitable for some plants but too frequent or too infrequent for others.",
            "Check the soil and plant condition each time; adjust for season, heat, pot size, and species.")

    # Height trend based on dated measurements.
    dated = [h for h in history if h.get("height_cm") is not None and h.get("observation_date")]
    dated.sort(key=lambda x: (x["observation_date"], x.get("id", 0)))
    if height is not None:
        earlier = [h for h in dated if h.get("id") != obs.get("id") and
                   (h["observation_date"] < obs["observation_date"] or
                    (h["observation_date"] == obs["observation_date"] and h.get("id", 0) < obs.get("id", 0)))]
        if earlier:
            prev = earlier[-1]
            delta = float(height) - float(prev["height_cm"])
            if delta <= 0.2:
                add("Growth check", "Height has barely changed",
                    f"The latest measurement is {delta:.1f} cm different from the previous record ({prev['height_cm']} cm on {prev['observation_date']}). Growth may be slow because of season, light, temperature, water, nutrients, or limited root space.",
                    "Measure from the same soil line to the same growing tip every 1–2 weeks. Check species-specific light needs, drainage, temperature, and whether the plant is in its growing season. Avoid adding fertiliser until basic conditions are checked.")
            else:
                add("Positive sign", "Height is increasing",
                    f"The plant is {delta:.1f} cm taller than the previous measurement ({prev['height_cm']} cm on {prev['observation_date']}).",
                    "Continue steady care and take measurements at similar intervals. Avoid making several changes at once if the plant otherwise looks healthy.")
        else:
            add("Build a baseline", "First height measurement",
                "There is not yet an earlier height record to compare against.",
                "Measure from the soil line to the same top point every 1–2 weeks. This makes it easier to tell normal slow growth from a genuine change.")

    # Light and placement
    if sunlight is not None:
        if sunlight < 2:
            add("Light check", "Very little direct sunlight recorded",
                f"You recorded about {sunlight:g} hours of sunlight per day. This may be too little for many fruiting or flowering plants, although some shade-loving plants prefer low light.",
                "Check the light needs for this species. If it needs more light, increase exposure gradually and avoid suddenly moving it into intense midday sun.")
        elif sunlight >= 7:
            add("Light check", "Long direct-sun exposure",
                f"You recorded about {sunlight:g} hours of sunlight per day. This suits some sun-loving plants but may scorch plants that prefer partial shade.",
                "Check species-specific light needs and watch for bleaching or crispy patches, especially after a sudden move outdoors.")
    if "indoor" in location or "window" in location:
        add("Placement", "Indoor light and airflow",
            "Light levels can be lower indoors than they appear, and air-conditioners or cold drafts can stress plants.",
            "Observe the plant's light across the day, rotate the pot occasionally if it leans, and keep it away from strong hot or cold drafts.")
    elif any(x in location for x in ["balcony", "terrace", "outdoor", "garden"]):
        add("Placement", "Outdoor conditions",
            "Outdoor plants may face strong afternoon sun, wind, heavy rain, or fast-drying pots.",
            "Check whether this species needs full sun or partial shade. Inspect soil moisture more often during hot or windy weather, but water only when needed.")

    if any(x in notes for x in ["pest", "insect", "web", "sticky", "mould", "mold"]):
        add("Monitor closely", "Possible pest or disease signs",
            "Your notes mention possible pests or mould. These symptoms can have several causes and need visual inspection.",
            "Inspect leaf undersides, stems, and soil surface. Isolate the plant if pests are present and identify the issue before applying any treatment.")

    if species:
        add("Personalisation note", f"Species recorded: {species}",
            "Care needs vary widely by species and sometimes by cultivar. This version uses your species entry as context but does not yet consult a live botanical database.",
            "For more specific advice, keep the species name accurate and add details such as pot size, soil mix, recent repotting, and when symptoms began.")

    if not recs:
        add("Start here", "Add more observations for better guidance",
            "The current entry does not contain enough specific signs for a focused recommendation.",
            "Record colour, height, location, sunlight hours, soil moisture, watering routine, and the plant species if known.")
    return recs

@app.route("/")
def index():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM observations ORDER BY observation_date DESC, id DESC").fetchall()
    plants = {}
    for row in rows:
        plants.setdefault(row["plant_name"], []).append(dict(row))
    return render_template("index.html", plants=plants, today=date.today().isoformat())

@app.route("/add", methods=["POST"])
def add_observation():
    form = request.form
    plant_name = form.get("plant_name", "").strip()
    observation_date = form.get("observation_date", "").strip()
    colour = form.get("colour", "").strip()
    location = form.get("location", "").strip()
    required = [plant_name, observation_date, colour, location]
    if not all(required):
        flash("Please fill in plant name, date, colour, and location.", "error")
        return redirect(url_for("index"))
    try:
        height = float(form.get("height_cm", "").strip()) if form.get("height_cm", "").strip() else None
        sunlight = float(form.get("sunlight_hours", "").strip()) if form.get("sunlight_hours", "").strip() else None
        if height is not None and height < 0: raise ValueError
        if sunlight is not None and not 0 <= sunlight <= 24: raise ValueError
    except ValueError:
        flash("Height must be non-negative and sunlight must be between 0 and 24 hours.", "error")
        return redirect(url_for("index"))
    with get_db() as conn:
        conn.execute("""INSERT INTO observations
        (plant_name, plant_species, observation_date, colour, height_cm, location, sunlight_hours, watering_frequency, soil_condition, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (plant_name, form.get("plant_species","").strip(), observation_date, colour, height,
         location, sunlight, form.get("watering_frequency","").strip(),
         form.get("soil_condition","").strip(), form.get("notes","").strip()))
    flash("Observation saved. Open its recommendations to see possible causes and next steps.", "success")
    return redirect(url_for("index"))

@app.route("/plant/<int:observation_id>")
def plant_detail(observation_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM observations WHERE id = ?", (observation_id,)).fetchone()
        if row is None:
            flash("Observation not found.", "error")
            return redirect(url_for("index"))
        history = conn.execute("SELECT * FROM observations WHERE plant_name = ? ORDER BY observation_date, id",
                               (row["plant_name"],)).fetchall()
    obs = dict(row)
    history = [dict(x) for x in history]
    recs = recommendations_for(obs, history)
    return render_template("detail.html", observation=obs, history=history, recs=recs)

@app.route("/delete/<int:observation_id>", methods=["POST"])
def delete_observation(observation_id):
    with get_db() as conn:
        conn.execute("DELETE FROM observations WHERE id = ?", (observation_id,))
    flash("Observation deleted.", "success")
    return redirect(url_for("index"))

@app.route("/export")
def export_csv():
    with get_db() as conn:
        rows = conn.execute("""SELECT plant_name, plant_species, observation_date, colour, height_cm, location,
        sunlight_hours, watering_frequency, soil_condition, notes FROM observations ORDER BY observation_date""").fetchall()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Plant name","Species","Date","Colour","Height (cm)","Location","Sunlight (hours/day)","Watering frequency","Soil condition","Notes"])
    writer.writerows([tuple(r) for r in rows])
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=garden_observations.csv"})

init_db()
if __name__ == "__main__":
    app.run(debug=True)
