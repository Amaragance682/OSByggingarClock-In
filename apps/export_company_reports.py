import os
import json
from collections import defaultdict
from datetime import datetime
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment
from openpyxl.styles.borders import Border, Side

from lib.utils import resource_path, load_task_config  # <- import the new loader

COMPANY_FOLDER = resource_path("Database/Fyrirtaeki")
EXPORT_FOLDER  = resource_path("Database/reports")

thin_gray = Border(
    left=Side(style="thin",  color="999999"),
    right=Side(style="thin", color="999999"),
    top=Side(style="thin",   color="999999"),
    bottom=Side(style="thin", color="999999"),
)
thick_black = Border(
    left=Side(style="medium", color="000000"),
    right=Side(style="medium",color="000000"),
    top=Side(style="medium",  color="000000"),
    bottom=Side(style="medium",color="000000"),
)

def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_users():
    return {u["id"]: u for u in read_json(resource_path("Database/users.json"))}

def ensure_folder(path):
    os.makedirs(path, exist_ok=True)

def format_date(iso):
    dt = datetime.fromisoformat(iso)
    day = dt.day
    suffix = "th" if 11 <= day <= 13 else {1:"st",2:"nd",3:"rd"}.get(day%10,"th")
    return f"{day}{suffix} of {dt.strftime('%B')}"

def compute_hours(start, end):
    delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    return round(delta.total_seconds()/3600, 2)

def export_company_to_excel(company_name):
    # — load the enriched task config —
    cfg = load_task_config()

    task_totals = defaultdict(float)
    day_shifts  = defaultdict(list)
    total_hours = 0.0

    current_month = datetime.now().strftime("%B")
    company_path   = os.path.join(COMPANY_FOLDER, company_name)
    report_path    = os.path.join(EXPORT_FOLDER, f"{company_name}_{current_month}.xlsx")
    ensure_folder(EXPORT_FOLDER)

    users = load_users()

    # — gather data from each employee log —
    for fn in os.listdir(company_path):
        if not fn.endswith(".json"):
            continue
        eid  = fn[:-5]
        user = users.get(eid, {"id":eid,"name":"Unknown"})
        logs = read_json(os.path.join(company_path, fn))
        for log in logs:
            if not log.get("clock_in") or not log.get("clock_out"):
                continue
            start    = log["clock_in"]
            end      = log["clock_out"]
            date_lbl = format_date(start)
            hours    = compute_hours(start, end)
            total_hours += hours
            task_name = log.get("task", "N/A")
            task_totals[task_name] += hours

            day_shifts[date_lbl].append([
                user["id"],
                user["name"],
                log.get("location","N/A"),
                task_name,
                start[11:16],
                end[11:16],
                hours
            ])

    # — build workbook —
    wb = Workbook()
    ws = wb.active
    ws.title = "Work Hours"

    bold        = Font(bold=True, size=12)
    header_font = Font(bold=True)
    section_f   = Font(bold=True, size=14)
    center      = Alignment(horizontal="center")
    row = 1

    if day_shifts:
        for date in sorted(day_shifts):
            if row>1: row += 2
            top_row = row

            # date header
            ws.merge_cells(
                start_row=row,
                start_column=1,
                end_row=row,
                end_column=7
            )
            c = ws.cell(row=row, column=1, value=date)
            c.font      = section_f
            c.alignment = Alignment(horizontal="left")
            row +=1

            # column headers
            headers=["Employee ID","Name","Location","Task","Clock In","Clock Out","Hours Worked"]
            ws.append(headers)
            for col in range(1,8):
                cell = ws.cell(row=row, column=col)
                cell.font      = header_font
                cell.alignment = center
            row+=1

            # shifts
            for rec in day_shifts[date]:
                ws.append(rec)
                row+=1

            # day total
            day_total = sum(r[-1] for r in day_shifts[date])
            ws.append([""]*6 + [f"Total: {round(day_total,2)} hrs"])
            ws.cell(row=row, column=7).font = bold

            bottom = row
            # gray border block
            for r in range(top_row, bottom+1):
                for c in range(1,8):
                    ws.cell(row=r,column=c).border = thin_gray
            row+=1
    else:
        ws.append([f"No shift data for {company_name} in {current_month}"])
        ws.cell(row=row, column=1).font = section_f
        row+=2

    # overall total
    ws.append([])
    row+=1
    ws.append([""]*6 + [f"Overall Total Hours: {round(total_hours,2)} hrs"])
    ws.cell(row=row+1, column=7).font = section_f
    row+=3

    # — Task Summary with completion state —
    ws.append(["Task Summary"])

    # “Task Summary” header (merge A–C for this row)
    ws.merge_cells(
        start_row=row,
        start_column=1,
        end_row=row,
        end_column=3
    )
    ws.cell(row=row, column=1).font = section_f
    row+=1

    # headers: now three columns
    ws.append(["Task Name","Total Hours","Completed?"])
    for col, _ in enumerate(["Task Name","Total Hours","Completed?"], start=1):
        ws.cell(row=row, column=col).font = header_font
        ws.cell(row=row, column=col).alignment = center
    row+=1

    if task_totals:
        # build a quick lookup of completion flags
        # scan every location in cfg:
        comp_states = {}
        for loc, comps in cfg.items():
            tasks = comps.get(company_name, [])
            for item in tasks:
                if isinstance(item, dict):
                    comp_states[item["name"]] = item.get("completed", False)
                else:
                    comp_states[item] = False

        for task, hrs in sorted(task_totals.items()):
            done = comp_states.get(task, False)
            ws.append([task, round(hrs,2), "Yes" if done else "No"])
            row+=1
    else:
        ws.append(["No tasks","0.00","—"])
        row+=1

    # autosize first three columns
    for col in range(1,4):
        letter = get_column_letter(col)
        maxlen = max(len(str(cell.value or "")) for cell in ws[letter])
        ws.column_dimensions[letter].width = max(12, min(maxlen+2, 30))

    wb.save(report_path)
    print(f"✅ Excel report written to: {report_path}")


def export_all_companies():
    for c in os.listdir(COMPANY_FOLDER):
        if os.path.isdir(os.path.join(COMPANY_FOLDER,c)):
            export_company_to_excel(c)


if __name__=="__main__":
    export_all_companies()
