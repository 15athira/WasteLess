from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import datetime
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# ---------------- DATABASE ----------------

def get_db_connection():
    conn = sqlite3.connect('mess_data.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            students INTEGER,
            cooked REAL,
            leftover REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------------- HELPER FUNCTIONS ----------------

def calculate_metrics(df):
    """Calculate all metrics for the dashboard"""
    if df.empty:
        return None
    
    df["consumption"] = df["cooked"] - df["leftover"]
    df["waste_percent"] = (df["leftover"] / df["cooked"]) * 100
    df["efficiency"] = 100 - df["waste_percent"]
    
    metrics = {
        'avg_waste': round(df["waste_percent"].mean(), 2),
        'total_loss': round(df["leftover"].sum() * 60, 2),  # ₹60 per kg
        'avg_efficiency': round(df["efficiency"].mean(), 2),
        'total_records': len(df),
        'total_consumption': round(df["consumption"].sum(), 2),
        'avg_consumption_per_student': round(df["consumption"].sum() / df["students"].sum(), 3)
    }
    
    return metrics

def get_chart_data():
    """Prepare data for Chart.js visualizations"""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM records ORDER BY date", conn)
    conn.close()
    
    if df.empty:
        return None
    
    df["consumption"] = df["cooked"] - df["leftover"]
    df["waste_percent"] = (df["leftover"] / df["cooked"]) * 100
    df["date"] = pd.to_datetime(df["date"])
    df["weekday"] = df["date"].dt.day_name()
    
    # Waste trend data
    waste_trend = {
        'labels': df["date"].dt.strftime('%Y-%m-%d').tolist(),
        'data': df["waste_percent"].round(2).tolist()
    }
    
    # Consumption analysis
    consumption_data = {
        'labels': df["date"].dt.strftime('%Y-%m-%d').tolist(),
        'cooked': df["cooked"].round(2).tolist(),
        'consumed': df["consumption"].round(2).tolist(),
        'leftover': df["leftover"].round(2).tolist()
    }
    
    # Weekday pattern
    weekday_avg = df.groupby("weekday")["waste_percent"].mean().round(2)
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekday_pattern = {
        'labels': [day for day in weekday_order if day in weekday_avg.index],
        'data': [weekday_avg[day] for day in weekday_order if day in weekday_avg.index]
    }
    
    # Student attendance pattern
    attendance_data = {
        'labels': df["date"].dt.strftime('%Y-%m-%d').tolist(),
        'data': df["students"].tolist()
    }
    
    return {
        'waste_trend': waste_trend,
        'consumption_data': consumption_data,
        'weekday_pattern': weekday_pattern,
        'attendance_data': attendance_data
    }

# ---------------- ROUTES ----------------

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/add', methods=['POST'])
def add_record():
    try:
        date = request.form['date']
        students = int(request.form['students'])
        cooked = float(request.form['cooked'])
        leftover = float(request.form['leftover'])
        
        # Validation
        if students <= 0:
            flash('Number of students must be positive', 'danger')
            return redirect('/')
        
        if cooked <= 0 or leftover < 0:
            flash('Cooked and leftover quantities must be non-negative', 'danger')
            return redirect('/')
        
        if leftover > cooked:
            flash('Leftover cannot be greater than cooked quantity', 'danger')
            return redirect('/')
        
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO records (date, students, cooked, leftover) VALUES (?, ?, ?, ?)",
            (date, students, cooked, leftover)
        )
        conn.commit()
        conn.close()
        
        flash('Record added successfully!', 'success')
        return redirect('/dashboard')
    
    except Exception as e:
        flash(f'Error adding record: {str(e)}', 'danger')
        return redirect('/')

@app.route('/dashboard')
def dashboard():
    try:
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM records ORDER BY date DESC", conn)
        conn.close()
        
        if df.empty:
            return render_template("dashboard.html", no_data=True)
        
        df["consumption"] = df["cooked"] - df["leftover"]
        df["waste_percent"] = (df["leftover"] / df["cooked"]) * 100
        df["efficiency"] = 100 - df["waste_percent"]
        
        metrics = calculate_metrics(df)
        
        # Format dataframe for display
        df_display = df.copy()
        df_display["consumption"] = df_display["consumption"].round(2)
        df_display["waste_percent"] = df_display["waste_percent"].round(2)
        df_display["efficiency"] = df_display["efficiency"].round(2)
        
        # Get current timestamp for "Last Updated"
        last_updated = datetime.datetime.now().strftime('%d %b %Y')
        
        return render_template("dashboard.html",
                             tables=df_display.to_html(classes='table table-striped table-hover', index=False),
                             metrics=metrics,
                             last_updated=last_updated,
                             no_data=False)
    
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'danger')
        return redirect('/')

@app.route('/analytics')
def analytics():
    try:
        chart_data = get_chart_data()
        
        if chart_data is None:
            return render_template("analytics.html", no_data=True)
        
        return render_template("analytics.html", 
                             chart_data=chart_data,
                             no_data=False)
    
    except Exception as e:
        flash(f'Error loading analytics: {str(e)}', 'danger')
        return redirect('/dashboard')

@app.route('/records')
def records():
    try:
        conn = get_db_connection()
        records = conn.execute("SELECT * FROM records ORDER BY date DESC").fetchall()
        conn.close()
        
        return render_template("records.html", records=records)
    
    except Exception as e:
        flash(f'Error loading records: {str(e)}', 'danger')
        return redirect('/dashboard')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_record(id):
    conn = get_db_connection()
    
    if request.method == 'POST':
        try:
            date = request.form['date']
            students = int(request.form['students'])
            cooked = float(request.form['cooked'])
            leftover = float(request.form['leftover'])
            
            # Validation
            if students <= 0 or cooked <= 0 or leftover < 0 or leftover > cooked:
                flash('Invalid input values', 'danger')
                return redirect(url_for('edit_record', id=id))
            
            conn.execute(
                "UPDATE records SET date=?, students=?, cooked=?, leftover=? WHERE id=?",
                (date, students, cooked, leftover, id)
            )
            conn.commit()
            conn.close()
            
            flash('Record updated successfully!', 'success')
            return redirect('/records')
        
        except Exception as e:
            flash(f'Error updating record: {str(e)}', 'danger')
            return redirect(url_for('edit_record', id=id))
    
    record = conn.execute("SELECT * FROM records WHERE id=?", (id,)).fetchone()
    conn.close()
    
    if record is None:
        flash('Record not found', 'danger')
        return redirect('/records')
    
    return render_template("edit.html", record=record)

@app.route('/delete/<int:id>')
def delete_record(id):
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM records WHERE id=?", (id,))
        conn.commit()
        conn.close()
        
        flash('Record deleted successfully!', 'success')
    
    except Exception as e:
        flash(f'Error deleting record: {str(e)}', 'danger')
    
    return redirect('/records')

# ---------------- ML TRAINING ----------------

def train_model():
    try:
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT * FROM records", conn)
        conn.close()
        
        if len(df) < 10:
            return None, None, "Need at least 10 records to train model"
        
        df["consumption"] = df["cooked"] - df["leftover"]
        df["date"] = pd.to_datetime(df["date"])
        df["weekday"] = df["date"].dt.weekday
        
        X = df[["students", "weekday"]]
        y = df["consumption"]
        
        model = LinearRegression()
        model.fit(X, y)
        
        score = model.score(X, y)
        
        return model, score, None
    
    except Exception as e:
        return None, None, str(e)

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if request.method == 'POST':
        try:
            students = int(request.form['students'])
            
            # Allow custom weekday selection or use today
            if 'weekday' in request.form and request.form['weekday']:
                weekday = int(request.form['weekday'])
            else:
                weekday = datetime.datetime.today().weekday()
            
            if students <= 0:
                flash('Number of students must be positive', 'warning')
                return render_template("prediction.html", prediction=None)
            
            model, score, error = train_model()
            
            if model is None:
                flash(error or 'Not enough data to train model (minimum 10 records required)', 'warning')
                return render_template("prediction.html", prediction=None)
            
            prediction = model.predict([[students, weekday]])
            
            # Calculate recommended cooking quantity (add safety margin)
            recommended_cooking = prediction[0] * 1.05  # 5% safety margin
            
            weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            return render_template("prediction.html",
                                 prediction=round(prediction[0], 2),
                                 recommended=round(recommended_cooking, 2),
                                 score=round(score * 100, 2),
                                 students=students,
                                 weekday_name=weekday_names[weekday])
        
        except Exception as e:
            flash(f'Error making prediction: {str(e)}', 'danger')
            return render_template("prediction.html", prediction=None)
    
    return render_template("prediction.html", prediction=None)

# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(debug=True)
