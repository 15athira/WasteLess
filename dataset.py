import pandas as pd
import numpy as np
from datetime import datetime, timedelta

data = []

start_date = datetime(2025, 1, 1)

for i in range(40):
    current_date = start_date + timedelta(days=i)
    
    weekday = current_date.weekday()
    
    # Student variation
    if weekday >= 5:  # weekend
        students = np.random.randint(400, 470)
    else:
        students = np.random.randint(480, 550)
    
    consumption_per_student = np.random.uniform(0.18, 0.22)
    
    consumption = students * consumption_per_student
    
    waste_percent = np.random.uniform(5, 15)
    leftover = consumption * (waste_percent / 100)
    
    cooked = consumption + leftover
    
    data.append([current_date.strftime("%Y-%m-%d"), students, cooked, leftover])

df = pd.DataFrame(data, columns=["date", "students", "cooked", "leftover"])

df.to_csv("sample_data.csv", index=False)

print("Dataset generated!")
