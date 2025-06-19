import os
import json
from datetime import datetime
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment

COMPANY_FOLDER = "Fyrirtaeki"
EXPORT_FOLDER = "reports"

def read_json(path):
    with open(path, "r") as f:
        return json.load(f)

def ensure_folder(path):
    os.makedirs(path, exist_ok=True)

def format_date(iso):
    return datetime.fromisoformat(iso).strftime("%Y-%m-%d")

def compute_hours(start, end):
    delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    return round(delta.total_seconds() / 3600, 2)

def export_company_to_excel(company_name):
    company_path = os.path.join(COMPANY_FOLDER, company_name)
    report_path = os.path.join(EXPORT_FOLDER, f"{company_name}.xlsx")
    ensure_folder(EXPORT_FOLDER)

    wb = Workbook()
    ws = wb.active
    ws.title = "Work Hours"

    # Header row
    headers = ["Employee", "Date", "Clock In", "Clock Out", "Hours Worked"]
    ws.append(headers)

    bold = Font(bold=True)
    for col in range(1, len(headers) + 1):
        ws.cell(row=1, column=col).font = bold
        ws.cell(row=1, column=col).alignment = Alignment(horizontal="center")

    row_counter = 2
    total_hours = 0.0

    for file in os.listdir(company_path):
        if not file.endswith(".json"):
            continue
        employee_id = file.replace(".json", "")
        logs = read_json(os.path.join(company_path, file))

        for log in logs:
            if log["clock_out"] is None:
                continue
            start = log["clock_in"]
            end = log["clock_out"]
            date = format_date(start)
            clock_in_time = start[11:]
            clock_out_time = end[11:]
            duration = compute_hours(start, end)
            total_hours += duration
            ws.append([employee_id, date, clock_in_time, clock_out_time, duration])
            row_counter += 1

    # Total hours
    ws.append(["", "", "", "Total Hours:", total_hours])
    ws.cell(row=row_counter + 1, column=4).font = bold
    ws.cell(row=row_counter + 1, column=5).font = bold

    # Autosize columns
    for col in range(1, 6):
        col_letter = get_column_letter(col)
        ws.column_dimensions[col_letter].auto_size = True

    wb.save(report_path)
    print(f"✅ Excel report created: {report_path}")

def export_all_companies():
    for company in os.listdir(COMPANY_FOLDER):
        company_path = os.path.join(COMPANY_FOLDER, company)
        if os.path.isdir(company_path):
            export_company_to_excel(company)

if __name__ == "__main__":
    export_all_companies()
