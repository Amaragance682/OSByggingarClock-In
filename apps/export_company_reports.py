import os
import json
from collections import defaultdict
from datetime import datetime
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment
from openpyxl.styles.borders import Border, Side

from lib.utils import (
    resource_path
)

COMPANY_FOLDER = resource_path("Database/Fyrirtaeki")
EXPORT_FOLDER = resource_path("Database/reports")

thin_gray = Border(
    left=Side(style="thin", color="999999"),
    right=Side(style="thin", color="999999"),
    top=Side(style="thin", color="999999"),
    bottom=Side(style="thin", color="999999"),
)

thick_black = Border(
    left=Side(style="medium", color="000000"),
    right=Side(style="medium", color="000000"),
    top=Side(style="medium", color="000000"),
    bottom=Side(style="medium", color="000000"),
)

def read_json(path):
    with open(path, "r") as f:
        return json.load(f)

def load_users():
    return {u["id"]: u for u in read_json(resource_path("Database/users.json"))}


def ensure_folder(path):
    os.makedirs(path, exist_ok=True)

def format_date(iso):
    dt = datetime.fromisoformat(iso)
    day = dt.day
    suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix} of {dt.strftime('%B')}"

def compute_hours(start, end):
    delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    return round(delta.total_seconds() / 3600, 2)

def export_company_to_excel(company_name):
    task_totals = defaultdict(float)
    day_shifts = defaultdict(list)
    total_hours = 0.0

    current_month = datetime.now().strftime("%B")
    company_path = os.path.join(COMPANY_FOLDER, company_name)
    report_path = os.path.join(EXPORT_FOLDER, f"{company_name}_{current_month}.xlsx")
    ensure_folder(EXPORT_FOLDER)

    users = load_users()

    for file in os.listdir(company_path):
        if not file.endswith(".json"):
            continue

        employee_id = file.replace(".json", "")
        user = users.get(employee_id, {"name": "Unknown", "id": employee_id})
        logs = read_json(os.path.join(company_path, file))

        for log in logs:
            if log.get("clock_out") is None or log.get("clock_in") is None:
                continue

            start = log["clock_in"]
            end = log["clock_out"]
            date = format_date(start)
            duration = compute_hours(start, end)
            total_hours += duration
            task_name = log.get("task", "N/A")
            task_totals[task_name] += duration

            day_shifts[date].append([
                user["id"],
                user["name"],
                log.get("location", "N/A"),
                task_name,
                start[11:16],
                end[11:16],
                duration
            ])

    # Start Excel building
    wb = Workbook()
    ws = wb.active
    ws.title = "Work Hours"

    bold = Font(bold=True, size=12)
    header_font = Font(bold=True)
    section_font = Font(bold=True, size=14)
    center_align = Alignment(horizontal="center")
    current_row = 1

    if day_shifts:
        for date in sorted(day_shifts.keys()):
            # Add spacing
            if current_row > 1:
                current_row += 2

            start_row = current_row  # <-- mark the top of this day section

            # Write date
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=7)
            cell = ws.cell(row=current_row, column=1, value=date)
            cell.font = section_font
            cell.alignment = Alignment(horizontal="left", vertical="center")
            current_row += 1

            # Write header
            headers = ["Employee ID", "Name", "Location", "Task", "Clock In", "Clock Out", "Hours Worked"]
            ws.append(headers)
            for col in range(1, 8):
                ws.cell(row=current_row, column=col).font = header_font
                ws.cell(row=current_row, column=col).alignment = center_align
            current_row += 1

            # Write shifts
            for shift in day_shifts[date]:
                ws.append(shift)
                current_row += 1

            # Total row
            day_total = sum(s[-1] for s in day_shifts[date])
            ws.append([""] * 6 + [f"Total: {round(day_total, 2)} hrs"])
            ws.cell(row=current_row, column=7).font = bold

            end_row = current_row  # <-- mark the bottom of this day section

            # Apply thin gray borders to this block
            for r in range(start_row, end_row + 1):
                for c in range(1, 8):
                    ws.cell(row=r, column=c).border = thin_gray

            current_row += 1
    else:
        # No shifts: write empty report headers
        ws.append(["No shift data available for this company in", current_month])
        ws.cell(row=current_row, column=1).font = section_font
        current_row += 2

    


    # Overall Total
    ws.append([])
    current_row += 1
    ws.append([""] * 6 + [f"Overall Total Hours: {round(total_hours, 2)} hrs"])
    ws.cell(row=current_row + 1, column=7).font = section_font
    current_row += 3

    # Task Summary
    ws.append(["Task Summary"])
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=2)
    ws.cell(row=current_row, column=1).font = section_font

    ws.append(["Task Name", "Total Hours"])
    ws.cell(row=current_row, column=1).font = header_font
    ws.cell(row=current_row, column=2).font = header_font
    current_row += 1

    if task_totals:
        for task, hours in sorted(task_totals.items()):
            ws.append([task, round(hours, 2)])
            current_row += 1
    else:
        ws.append(["No task data", "0.00"])
        current_row += 1

    # Autosize columns
    for col in range(1, 8):
        col_letter = get_column_letter(col)
        max_length = 0
        for cell in ws[col_letter]:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        ws.column_dimensions[col_letter].width = max(12, min(max_length + 2, 30))

    wb.save(report_path)
    print(f"✅ Excel report created: {report_path}")

def export_all_companies():
    for company in os.listdir(COMPANY_FOLDER):
        company_path = os.path.join(COMPANY_FOLDER, company)
        if os.path.isdir(company_path):
            export_company_to_excel(company)

if __name__ == "__main__":
    export_all_companies()
