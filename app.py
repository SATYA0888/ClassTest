import io
import zipfile, zipfile, re, os
from pathlib import Path
from datetime import datetime
import pandas as pd

def format_seat_no(value):
    """Display numeric seat numbers without Excel/Pandas .0 suffixes."""
    if pd.isna(value):
        return ""
    s = str(value).strip()
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
        return str(f).rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return s


def format_roll_no(value):
    if pd.isna(value):
        return ""
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _pdf_prepare_df(df):
    """Prepare PDF rows without dropping entries because of column-name variants."""
    if df is None:
        return pd.DataFrame()
    d = df.copy()
    # Normalize common column names while retaining all rows.
    aliases = {
        "Name": ["Student Name", "Name", "Student"],
        "Roll No": ["Roll No", "Roll Number", "Enrollment No", "Enrollment Number", "Roll"],
        "Course": ["Course", "Program", "Course Name"],
        "Seat No": ["Seat No.", "Seat No", "Seat Number", "Seat"],
        "Room No": ["Room No.", "Room No", "Room Number", "Room"],
        "Answer Sheet No": ["Answer Sheet No.", "Answer Sheet No", "Answer Sheet Number", "AnswerSheet No"],
    }
    for target, names in aliases.items():
        if target in d.columns:
            continue
        for name in names:
            if name in d.columns:
                d[target] = d[name]
                break
        if target not in d.columns:
            d[target] = ""
    d["Seat No"] = d["Seat No"].apply(format_seat_no)
    d["Roll No"] = d["Roll No"].apply(lambda x: "" if pd.isna(x) else str(x).replace(".0","") if str(x).endswith(".0") else str(x))
    d["Name"] = d["Name"].fillna("").astype(str)
    d["Course"] = d["Course"].fillna("").astype(str)
    d["Room No"] = d["Room No"].fillna("").astype(str)
    d["Answer Sheet No"] = d["Answer Sheet No"].apply(format_seat_no)
    return d.reset_index(drop=True)

import streamlit as st

st.set_page_config(page_title='ODD Minor Exam Manager', page_icon='🎓', layout='wide')

# ---------------- PDF helpers ----------------
def pdf_table(title, subtitle, df, landscape_mode=False, rows_per_page=28):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape, portrait
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.units import mm

    buf = io.BytesIO()
    page = A4 if landscape_mode else A4
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=8*mm, leftMargin=8*mm, topMargin=8*mm, bottomMargin=8*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('t', parent=styles['Title'], alignment=TA_CENTER, fontSize=14, leading=17)
    sub_style = ParagraphStyle('s', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8, leading=10)
    cell = ParagraphStyle('cell', parent=styles['Normal'], fontSize=7, leading=8)
    head = ParagraphStyle('head', parent=styles['Normal'], fontSize=7, leading=8, alignment=TA_CENTER)
    story=[]
    if subtitle is None: subtitle=''
    chunks=[df.iloc[i:i+rows_per_page] for i in range(0,len(df),rows_per_page)] or [df]
    for pi,chunk in enumerate(chunks):
        story += [Paragraph(title, title_style), Paragraph(subtitle, sub_style), Spacer(1,5*mm)]
        data=[[Paragraph(str(c),head) for c in chunk.columns]]
        for row in chunk.itertuples(index=False):
            data.append([Paragraph('' if pd.isna(v) else str(v), cell) for v in row])
        widths=[]
        n=len(chunk.columns)
        avail=page[0]-16*mm
        widths=[avail/n]*n if n else []
        t=Table(data,colWidths=widths,repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eef5')),
            ('GRID',(0,0),(-1,-1),0.4,colors.grey),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('ALIGN',(0,0),(-1,0),'CENTER'),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f8fafc')]),
            ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
        ]))
        story.append(t)
        if pi < len(chunks)-1: story.append(PageBreak())
    doc.build(story)
    return buf.getvalue()


def _roll(value):
    """Return a clean printable roll/enrollment number."""
    return normalize_roll(value)

def _add_seat_numbers(df):
    """Ensure a clean integer-style Seat No column.
    Preserve an existing Seat No/Seat No./Seat Number column; generate 1,2,3...
    only when no usable seat number is present.
    """
    out = df.copy()
    seat_col = next((c for c in ['Seat No', 'Seat No.', 'Seat Number'] if c in out.columns), None)
    if seat_col is None:
        out['Seat No'] = pd.Series(range(1, len(out) + 1), index=out.index, dtype='int64')
    else:
        if seat_col != 'Seat No':
            out = out.rename(columns={seat_col: 'Seat No'})
        vals = out['Seat No']
        missing = vals.isna() | vals.astype(str).str.strip().isin(['', 'nan', 'None', 'NaN'])
        if missing.any():
            generated = pd.Series(range(1, len(out) + 1), index=out.index)
            out.loc[missing, 'Seat No'] = generated.loc[missing]
        out['Seat No'] = out['Seat No'].apply(format_seat_no)
    return out

def pdf_room_attendance(df, room, date_str, shift):
    """Generate a populated A4 portrait room attendance PDF.
    Every input row is represented exactly once; only the requested display
    columns and seat-number formatting are applied.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.units import mm

    if df is None or df.empty:
        return None

    d = _pdf_prepare_df(df)
    d = _add_seat_numbers(d)

    # Preserve source values as strings. Do not normalize roll numbers,
    # names, courses, rooms, or answer-sheet values.
    out = pd.DataFrame(index=d.index)
    out['Sr. No'] = range(1, len(d) + 1)
    out['Seat No'] = d['Seat No'].map(format_seat_no)
    out['Name'] = d['Name'].map(lambda x: '' if pd.isna(x) else str(x))
    out['Roll No'] = d['Roll No'].map(lambda x: '' if pd.isna(x) else str(x))
    out['Course'] = d['Course'].map(lambda x: '' if pd.isna(x) else str(x))
    out['Answer Sheet No'] = d['Answer Sheet No'].map(lambda x: '' if pd.isna(x) else str(x))
    out['Signature'] = ''

    # Hard guarantee: never create a blank PDF when source rows exist.
    if len(out) != len(df) or len(out) == 0:
        return None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, rightMargin=5*mm, leftMargin=5*mm,
        topMargin=7*mm, bottomMargin=7*mm
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('roomtitle_final', parent=styles['Title'], alignment=TA_CENTER, fontSize=12, leading=14)
    sub_style = ParagraphStyle('roomsub_final', parent=styles['Normal'], alignment=TA_CENTER, fontSize=7.5, leading=9)
    cell = ParagraphStyle('roomcell_final', parent=styles['Normal'], fontSize=6.2, leading=7)
    head = ParagraphStyle('roomhead_final', parent=styles['Normal'], fontSize=6.2, leading=7, alignment=TA_CENTER)

    story=[]
    chunks=[out.iloc[i:i+24] for i in range(0, len(out), 24)]
    widths=[9*mm,16*mm,42*mm,25*mm,30*mm,27*mm,38*mm]

    for pi, chunk in enumerate(chunks):
        story += [
            Paragraph('ROOM-WISE ATTENDANCE SHEET', title_style),
            Paragraph(
                f'Room: {room} | Date: {date_str} | Shift: {shift} | Total Students: {len(out)}',
                sub_style
            ),
            Spacer(1,3*mm)
        ]
        data=[[Paragraph(str(c),head) for c in out.columns]]
        for row in chunk.itertuples(index=False):
            data.append([
                Paragraph('' if pd.isna(v) else str(v), cell)
                for v in row
            ])
        tab=Table(data,colWidths=widths,repeatRows=1)
        tab.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eef5')),
            ('GRID',(0,0),(-1,-1),0.4,colors.grey),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('ALIGN',(0,0),(-1,0),'CENTER'),
            ('ALIGN',(0,0),(1,-1),'CENTER'),
            ('ALIGN',(3,0),(5,-1),'CENTER'),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f8fafc')]),
            ('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),
            ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)
        ]))
        story.append(tab)
        if pi < len(chunks)-1:
            story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()


def pdf_course_allocation(df, course, date_str, shift):
    """Generate one populated A4 portrait course-wise allocation PDF."""
    from reportlab.lib.pagesizes import A4

    if df is None or df.empty:
        return None

    d = _pdf_prepare_df(df)
    d = _add_seat_numbers(d)

    # Preserve all source values. Only seat number gets the requested
    # integer-style display (1, 2, 3 instead of 1.0, 2.0, 3.0).
    out = pd.DataFrame(index=d.index)
    out['Sr. No'] = range(1, len(d) + 1)
    out['Name'] = d['Name'].map(lambda x: '' if pd.isna(x) else str(x))
    out['Roll No'] = d['Roll No'].map(lambda x: '' if pd.isna(x) else str(x))
    out['Seat No'] = d['Seat No'].map(format_seat_no)
    out['Room No'] = d['Room No'].map(lambda x: '' if pd.isna(x) else str(x))

    if len(out) != len(df) or len(out) == 0:
        return None

    return pdf_table(
        f'COURSE-WISE ALLOCATION — {course}',
        f'Date: {date_str} | Shift: {shift} | Total Students: {len(out)}',
        out, landscape_mode=False, rows_per_page=28
    )


def pdf_course_summary(df, course, date_str, shift):
    return pdf_course_allocation(df,course,date_str,shift)

# ---------------- parsing ----------------
def clean(x): return re.sub(r'\s+',' ',str(x).strip())
def parse_context(path):
    m=re.search(r'(20\d{2}-\d{2}-\d{2})_([IV]+)', path)
    if m:
        try: d=datetime.strptime(m.group(1),'%Y-%m-%d').date()
        except: d=None
        return d,m.group(2)
    return None,''

def read_excel_bytes(z,name,sheet_name=None,header=None):
    return pd.read_excel(io.BytesIO(z.read(name)),sheet_name=sheet_name,header=header)

@st.cache_data(show_spinner=False)
def load_all(blob):
    z=zipfile.ZipFile(io.BytesIO(blob))
    names=z.namelist()
    attendance=[]; course_summary=[]; student_lists=[]; seating=[]; datesheet=pd.DataFrame(); files=[]
    for name in names:
        if not name.lower().endswith(('.xlsx','.xls')): continue
        base=Path(name).name
        files.append(name)
        low=base.lower()
        try:
            xl=pd.ExcelFile(io.BytesIO(z.read(name)))
            if 'final classtest' in low:
                # first sheet, detect header row
                raw=pd.read_excel(io.BytesIO(z.read(name)),sheet_name=xl.sheet_names[0],header=None)
                hi=None
                for i in range(min(30,len(raw))):
                    vals=[clean(v).lower() for v in raw.iloc[i].tolist()]
                    if 'paper code' in vals and 'paper name' in vals: hi=i; break
                if hi is not None:
                    d=raw.iloc[hi+1:].copy(); d.columns=[clean(v) for v in raw.iloc[hi].tolist()]
                    d=d.dropna(how='all'); datesheet=d
                    if 'Date of Exam' in d: d['Date of Exam']=pd.to_datetime(d['Date of Exam'],errors='coerce')
                    if 'Student Count' in d: d['Student Count']=pd.to_numeric(d['Student Count'],errors='coerce')
            elif 'attendance_all_rooms' in low:
                date,shift=parse_context(name)
                for s in xl.sheet_names:
                    d=pd.read_excel(io.BytesIO(z.read(name)),sheet_name=s)
                    d.columns=[clean(c) for c in d.columns]
                    d['Date']=date; d['Shift']=shift; d['Room']=s.replace('Room_','')
                    attendance.append(d)
            elif 'course_room_summary' in low:
                date,shift=parse_context(name)
                raw=pd.read_excel(io.BytesIO(z.read(name)),sheet_name=xl.sheet_names[0],header=None)
                raw=raw.dropna(how='all')
                if len(raw)>=2:
                    raw.columns=[clean(v) for v in raw.iloc[0].tolist()]
                    d=raw.iloc[1:].copy(); d=d.loc[:,~d.columns.duplicated()]
                    d['Date']=date; d['Shift']=shift
                    course_summary.append(d)
            elif 'course_wise_student_list' in low:
                date,shift=parse_context(name)
                for s in xl.sheet_names:
                    d=pd.read_excel(io.BytesIO(z.read(name)),sheet_name=s)
                    d.columns=[clean(c) for c in d.columns]
                    d['Date']=date; d['Shift']=shift; d['Course']=s
                    student_lists.append(d)
            elif 'room_seating_plan' in low:
                date,shift=parse_context(name)
                for s in xl.sheet_names:
                    d=pd.read_excel(io.BytesIO(z.read(name)),sheet_name=s)
                    d.columns=[clean(c) for c in d.columns]
                    d['Date']=date; d['Shift']=shift
                    seating.append(d)
        except Exception:
            pass
    att=pd.concat(attendance,ignore_index=True) if attendance else pd.DataFrame()
    cs=pd.concat(course_summary,ignore_index=True) if course_summary else pd.DataFrame()
    sl=pd.concat(student_lists,ignore_index=True) if student_lists else pd.DataFrame()
    sp=pd.concat(seating,ignore_index=True) if seating else pd.DataFrame()
    return names,datesheet,att,cs,sl,sp,files

# ---------------- app ----------------
st.title('🎓 ODD Minor Exam — Interactive Management System')
st.caption('Dates • Shifts • Courses • Rooms • Seating • Attendance • PDF reports')

up=st.sidebar.file_uploader('Upload ODD Minor Exam 2026 ZIP',type=['zip'])
default=Path('ODD Minor Exam 2026.zip')
if up: blob=up.getvalue(); source=up.name
elif default.exists(): blob=default.read_bytes(); source=default.name
else:
    st.warning('Upload the ZIP file from the sidebar.'); st.stop()

names,datesheet,att,cs,sl,sp,files=load_all(blob)

# DET Excel upload: Roll No. + Student Name -> append (det) to matching records.
def normalize_roll(v):
    if pd.isna(v): return ''
    s=str(v).strip()
    try:
        f=float(s)
        if f.is_integer(): return str(int(f))
    except Exception:
        pass
    return s

@st.cache_data(show_spinner=False)
def read_det_excel(file_bytes):
    sheets=pd.read_excel(io.BytesIO(file_bytes),sheet_name=None)
    frames=[]
    for sheet_name,raw in sheets.items():
        if raw.empty: continue
        raw=raw.dropna(how='all').copy()
        mapping={}
        for c in raw.columns:
            lc=str(c).strip().lower()
            if any(x in lc for x in ['roll no','roll number','rollno','enrollment','enrolment']):
                mapping[c]='Roll No'
            elif any(x in lc for x in ['student name','name of student','name']):
                mapping[c]='Student Name'
        df=raw.rename(columns=mapping)
        if 'Roll No' in df.columns and 'Student Name' in df.columns:
            df=df[['Roll No','Student Name']].copy()
            df['Roll No']=df['Roll No'].apply(normalize_roll)
            df['Student Name']=df['Student Name'].fillna('').astype(str).str.strip()
            df=df[df['Roll No'].ne('')]
            df['Source Sheet']=sheet_name
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=['Roll No','Student Name','Source Sheet'])
    return pd.concat(frames,ignore_index=True).drop_duplicates('Roll No',keep='last')

st.sidebar.header('DET / Student Name Update')
det_file=st.sidebar.file_uploader(
    'Upload Excel: Roll No. + Student Name',
    type=['xlsx','xls'],
    key='det_excel'
)
det_master=pd.DataFrame(columns=['Roll No','Student Name','Source Sheet'])
if det_file:
    try:
        det_master=read_det_excel(det_file.getvalue())
        if det_master.empty:
            st.sidebar.error('No Roll No. + Student Name columns found.')
        else:
            st.sidebar.success(f'{len(det_master)} roll numbers loaded')
    except Exception as e:
        st.sidebar.error(f'Excel error: {e}')

def _find_roll_column(df):
    """Find a roll/enrollment-number column across different source workbooks."""
    if df.empty: return None
    preferred=['Enrollment No','Roll No','Roll Number','RollNo','Enrollment Number','Enrolment No','Enrolment Number']
    for c in preferred:
        if c in df.columns: return c
    for c in df.columns:
        lc=str(c).strip().lower().replace('_',' ')
        if ('roll' in lc and ('no' in lc or 'number' in lc)) or 'enrollment' in lc or 'enrolment' in lc:
            return c
    return None

def _find_name_column(df):
    if df.empty: return None
    for c in ['Name','Student Name','Name of Student','Student_Name']:
        if c in df.columns: return c
    for c in df.columns:
        lc=str(c).strip().lower()
        if 'name' in lc and 'course' not in lc: return c
    return None

def apply_det(df, roll_col=None, name_col=None):
    """Append (det) to every matching student's displayed name, using Roll No only.
    The student's original name is preserved; (det) is added exactly once.
    """
    if df.empty or det_master.empty: return df.copy()
    roll_col = roll_col if roll_col in df.columns else _find_roll_column(df)
    name_col = name_col if name_col in df.columns else _find_name_column(df)
    if not roll_col or not name_col: return df.copy()
    out=df.copy()
    rolls=set(det_master['Roll No'].apply(normalize_roll).astype(str))
    hit=out[roll_col].apply(normalize_roll).isin(rolls)
    original=out[name_col].fillna('').astype(str).str.strip()
    out.loc[hit,name_col]=original.loc[hit].str.replace(r'\s*\(det\)\s*$','',regex=True).str.rstrip()+' (det)'
    return out

# Apply DET marking BEFORE every dashboard/report/filter operation.
att=apply_det(att)
sl=apply_det(sl)
sp=apply_det(sp)
cs=apply_det(cs)

# DET verification preview: makes the name change visible immediately after upload.
if not det_master.empty:
    _det_hits=[]
    for _df,_label in [(att,'Room/Attendance'),(sl,'Course Student List'),(sp,'Seating')]:
        if _df.empty: continue
        rc=_find_roll_column(_df); nc=_find_name_column(_df)
        if rc and nc:
            _x=_df[_df[rc].apply(normalize_roll).isin(set(det_master['Roll No'].astype(str)))][[rc,nc]].copy()
            if not _x.empty:
                _x.columns=['Roll No','Student Name']; _x['Source']=_label; _det_hits.append(_x)
    if _det_hits:
        _det_preview=pd.concat(_det_hits,ignore_index=True).drop_duplicates(['Roll No','Source'])
        st.sidebar.success(f"DET applied: {len(_det_preview)} matching record(s) found")
        with st.sidebar.expander('Preview changed student names',expanded=False):
            st.dataframe(_det_preview[['Roll No','Student Name']],use_container_width=True,hide_index=True)

# filters
st.sidebar.header('Global Filters')
def opts(df,col): return sorted([x for x in df[col].dropna().astype(str).unique() if x]) if col in df else []
dates=sorted(att['Date'].dropna().unique()) if 'Date' in att else []
shifts=opts(att,'Shift'); rooms=opts(att,'Room'); courses=opts(att,'Course')
sel_date=st.sidebar.selectbox('Date', ['All']+ [str(x) for x in dates])
sel_shift=st.sidebar.selectbox('Shift', ['All']+shifts)
sel_room=st.sidebar.selectbox('Room', ['All']+rooms)
sel_course=st.sidebar.selectbox('Course', ['All']+courses)

af=att.copy()
if sel_date!='All': af=af[af['Date'].astype(str)==sel_date]
if sel_shift!='All': af=af[af['Shift'].astype(str)==sel_shift]
if sel_room!='All': af=af[af['Room'].astype(str)==sel_room]
if sel_course!='All': af=af[af['Course'].astype(str)==sel_course]

c1,c2,c3,c4,c5=st.columns(5)
c1.metric('Exam Dates',len(dates))
c2.metric('Rooms',len(rooms))
c3.metric('Attendance Records',len(af))
c4.metric('Courses',len(courses))
c5.metric('Source Excel Files',len(files))



SHIFT_TIME = {
    "I": "09:00 AM - 10:00 AM",
    "II": "11:30 AM - 12:30 PM",
    "III": "01:00 PM - 02:00 PM",
    "IV": "03:00 PM - 04:00 PM",
}

def normalize_schedule_date(v):
    try:
        d=pd.to_datetime(v)
        # The supplied workbook stores 05/10/2026 ... 09/10/2026 as
        # 2026-05-10 ... 2026-09-10, while its Validation sheet confirms
        # the intended exam range is 05 October 2026 to 09 October 2026.
        if d.year == 2026 and d.month in [5,6,7,8,9] and d.day == 10:
            return f"2026-10-{d.month:02d}"
        return d.strftime("%Y-%m-%d")
    except Exception:
        return str(v)

def course_group_from_program(program):
    s=str(program).upper()
    sem = ""
    for n in ["VII","V","III","I"]:
        if f"{n} SEM" in s or f", {n}" in s:
            sem=n; break
    if "B.TECH" in s or "BTECH" in s: return f"BTech {sem}".strip()
    if "BCA" in s: return f"BCA {sem}".strip()
    if "MCA" in s: return f"MCA {sem}".strip()
    if "DIP" in s or "DIPLOMA" in s: return f"Dip {sem}".strip()
    return ""

def scheduled_papers(date_value, shift_value):
    if datesheet.empty or "Date of Exam" not in datesheet.columns or "Time" not in datesheet.columns:
        return pd.DataFrame()
    d=datesheet.copy()
    d["_ExamDate"]=d["Date of Exam"].apply(normalize_schedule_date)
    d=d[d["_ExamDate"].astype(str)==str(date_value)]
    if shift_value!="All":
        target=SHIFT_TIME.get(str(shift_value),"")
        if target:
            d=d[d["Time"].astype(str).str.replace("–","-",regex=False).str.strip()==target]
    d["_CourseGroup"]=d["Program / Branch / Semester"].apply(course_group_from_program) if "Program / Branch / Semester" in d.columns else ""
    return d

def attendance_for_actual_papers(date_value, shift_value):
    if att.empty: return pd.DataFrame(), pd.DataFrame()
    d=att.copy()
    d=d[d["Date"].astype(str)==str(date_value)]
    if shift_value!="All": d=d[d["Shift"].astype(str)==str(shift_value)]
    sched=scheduled_papers(date_value,shift_value)
    if sched.empty: return pd.DataFrame(),sched
    eligible=set(sched["_CourseGroup"].astype(str))
    d=d[d["Course"].astype(str).isin(eligible)].copy()
    return d,sched

def _safe_filename(value):
    value = str(value).strip()
    value = re.sub(r'[<>:"/\\|?*]+', '_', value)
    value = re.sub(r'\s+', '_', value)
    return value[:150] or "file"

def _make_zip(files_dict):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for filename, pdf_bytes in files_dict.items():
            z.writestr(filename, pdf_bytes)
    return buf.getvalue()

def build_room_pdfs_for_date(date_value, shift_value):
    d,sched=attendance_for_actual_papers(date_value,shift_value)
    if d.empty or "Room" not in d.columns: return {}
    result={}
    for room in sorted(d["Room"].dropna().astype(str).unique()):
        rv=d[d["Room"].astype(str)==room].copy()
        pdf=pdf_room_attendance(rv,room,str(date_value),str(shift_value))
        if not pdf:
            continue
        result[f"{_safe_filename(room)}_{_safe_filename(shift_value)}_{_safe_filename(date_value)}.pdf"]=pdf
    return result

def build_course_room_pdfs_for_date(date_value, shift_value, selected_courses=None):
    """Create one populated A4-portrait PDF per eligible course."""
    d, sched = attendance_for_actual_papers(date_value, shift_value)
    if d.empty or "Course" not in d.columns:
        return {}
    if selected_courses:
        d = d[d["Course"].astype(str).isin([str(x) for x in selected_courses])].copy()
    result = {}
    for course, rv in d.groupby("Course", dropna=False):
        course = str(course)
        rv = rv.copy()
        if rv.empty:
            continue
        pdf = pdf_course_allocation(rv, course, str(date_value), str(shift_value))
        if pdf:
            result[f"{_safe_filename(course)}_{_safe_filename(shift_value)}_{_safe_filename(date_value)}.pdf"] = pdf
    return result

st.subheader("📦 Bulk PDF Downloads — Scheduled Papers Only")
st.caption("Select a date and shift. Only papers actually occurring at that time are included. Course-wise and room-wise PDFs are A4 Portrait; seat numbers are displayed as 1, 2, 3...")

available_dates=sorted(att["Date"].dropna().astype(str).unique().tolist()) if not att.empty else []
available_shifts=sorted(att["Shift"].dropna().astype(str).unique().tolist()) if not att.empty else []

if not available_dates:
    st.warning("No attendance dates are available.")
else:
    c1,c2=st.columns(2)
    bulk_date=c1.selectbox("Exam Date",available_dates,key="bulk_date")
    bulk_shift=c2.selectbox("Shift",["All"]+available_shifts,key="bulk_shift")

    scheduled=scheduled_papers(bulk_date,bulk_shift)
    actual,sched=attendance_for_actual_papers(bulk_date,bulk_shift)

    st.markdown("### 📋 Paper(s) actually scheduled")
    if scheduled.empty:
        st.error("No paper is scheduled in the Class Test Datesheet for this date/shift. Therefore, no room PDFs or course allocation PDFs will be generated.")
    else:
        show=[c for c in ["Program / Branch / Semester","Paper Code","Paper Name","Time","Student Count"] if c in scheduled.columns]
        st.dataframe(scheduled[show],use_container_width=True,hide_index=True)

        rooms=sorted(actual["Room"].dropna().astype(str).unique()) if not actual.empty else []
        st.metric("Eligible rooms",len(rooms))
        st.write("Eligible rooms: " + (", ".join(rooms) if rooms else "None"))

        st.markdown("### 1️⃣ Room-wise attendance PDFs")
        st.write("Only rooms containing students from a program/semester having a paper in the selected date + shift are included.")
        st.code("ROOM_SHIFT_DATE.pdf")

        if st.button("📄 Generate & Download Eligible Room PDFs",key="bulk_room_pdf"):
            with st.spinner("Checking papers and generating room PDFs..."):
                files_dict=build_room_pdfs_for_date(bulk_date,bulk_shift)
                if files_dict:
                    st.download_button(
                        "⬇️ Download Eligible Room PDFs (ZIP)",
                        _make_zip(files_dict),
                        f"Room_Attendance_{_safe_filename(bulk_date)}_{_safe_filename(bulk_shift)}.zip",
                        "application/zip",key="download_room_zip")
                    st.success(f"{len(files_dict)} room PDF(s) generated — only scheduled-paper rooms.")
                else:
                    st.warning("No eligible room allocation was found.")

        st.markdown("---")
        st.markdown("### 2️⃣ Course-wise allocation PDFs")
        course_values=sorted(actual["Course"].dropna().astype(str).unique()) if not actual.empty else []
        selected_courses=st.multiselect("Courses/program groups",course_values,default=course_values,key="bulk_courses")
        pair_count=actual[actual["Course"].astype(str).isin(selected_courses)]["Course"].nunique() if selected_courses and not actual.empty else 0
        st.metric("Eligible course PDFs",pair_count)
        st.code("COURSE_SHIFT_DATE.pdf")

        if st.button("📚 Generate & Download Eligible Course PDFs",key="bulk_course_pdf"):
            with st.spinner("Generating course-wise allocation PDFs..."):
                files_dict=build_course_room_pdfs_for_date(bulk_date,bulk_shift,selected_courses)
                if files_dict:
                    st.download_button(
                        "⬇️ Download Eligible Course PDFs (ZIP)",
                        _make_zip(files_dict),
                        f"Course_Wise_Allocation_{_safe_filename(bulk_date)}_{_safe_filename(bulk_shift)}.zip",
                        "application/zip",key="download_course_zip")
                    st.success(f"{len(files_dict)} course-wise PDF(s) generated.")
                else:
                    st.warning("No eligible course allocation was found.")

        st.markdown("---")
        st.markdown("### 3️⃣ One-click: ALL eligible PDFs")
        if st.button("📦 Generate & Download ALL Eligible PDFs",key="bulk_all_pdf"):
            with st.spinner("Generating only PDFs for papers actually occurring..."):
                room_files=build_room_pdfs_for_date(bulk_date,bulk_shift)
                course_files=build_course_room_pdfs_for_date(bulk_date,bulk_shift,selected_courses)
                combined={}
                for name,data in room_files.items(): combined[f"Room_Attendance/{name}"]=data
                for name,data in course_files.items(): combined[f"Course_Wise_Allocation/{name}"]=data
                if combined:
                    st.download_button(
                        "⬇️ Download ALL Eligible PDFs (ZIP)",
                        _make_zip(combined),
                        f"Exam_PDFs_{_safe_filename(bulk_date)}_{_safe_filename(bulk_shift)}.zip",
                        "application/zip",key="download_all_zip")
                    st.success(f"{len(combined)} eligible PDF(s) generated.")
                else:
                    st.warning("No eligible PDFs found.")

