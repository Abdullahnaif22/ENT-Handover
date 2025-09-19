from datetime import datetime, date

def dob_to_age(dob_str: str):
    try:
        d = datetime.strptime(dob_str, "%Y-%m-%d").date()
        t = date.today()
        return t.year - d.year - ((t.month, t.day) < (d.month, d.day))
    except Exception:
        return None

def pill(text: str, colour: str) -> str:
    return f"<span class='pill' style='border-color:{colour};color:{colour}'>{text}</span>"

def priority_pill(p: str) -> str:
    return pill(p, {"Urgent":"#e11d48","Soon":"#f59e0b","Routine":"#10b981"}.get(p,"#64748b"))

def status_pill(s: str) -> str:
    return pill(s, {"Open":"#3b82f6","In Progress":"#a855f7","Done":"#10b981"}.get(s,"#64748b"))
