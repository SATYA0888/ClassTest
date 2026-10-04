import io
import zipfile, zipfile, re, os
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st

st.set_page_config(page_title='ODD Minor Exam Manager', page_icon='🎓', layout='wide')

# ---------------- PDF helpers ----------------
def pdf_table(title, subtitle, df, landscape_mode=True, rows_per_page=28):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape, portrait
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.units import mm

    buf = io.BytesIO()
    page = landscape(A4) if landscape_mode else portrait(A4)
    doc = SimpleDocTemplate(buf, pagesize=page, rightMargin=8*mm, leftMargin=8*mm, topMargin=8*mm, bottomMargin=8*mm)
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

def pdf_room_attendance(df, room, date_str, shift):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.units import mm

    # Exact requested columns: Sr. No | Seat No | Name | Roll No | Course | Answer Sheet No | Signature
    d=_add_seat_numbers(df)
    out=pd.DataFrame()
    out['Sr. No']=range(1,len(d)+1)
    out['Seat No']=d['Seat No'].astype(str) if 'Seat No' in d else ''
    out['Name']=d['Name'].astype(str) if 'Name' in d else ''
    out['Roll No']=d['Enrollment No'].apply(_roll) if 'Enrollment No' in d else ''
    out['Course']=d['Course'].astype(str) if 'Course' in d else ''
    out['Answer Sheet No']=d['Answer Sheet No'].fillna('').astype(str) if 'Answer Sheet No' in d else ''
    out['Signature']=''

    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=5*mm,leftMargin=5*mm,topMargin=7*mm,bottomMargin=7*mm)
    styles=getSampleStyleSheet()
    title_style=ParagraphStyle('roomtitle2',parent=styles['Title'],alignment=TA_CENTER,fontSize=12,leading=14)
    sub_style=ParagraphStyle('roomsub2',parent=styles['Normal'],alignment=TA_CENTER,fontSize=7.5,leading=9)
    cell=ParagraphStyle('roomcell2',parent=styles['Normal'],fontSize=6.2,leading=7)
    head=ParagraphStyle('roomhead2',parent=styles['Normal'],fontSize=6.2,leading=7,alignment=TA_CENTER)
    story=[]
    chunks=[out.iloc[i:i+24] for i in range(0,len(out),24)] or [out]
    widths=[9*mm,16*mm,42*mm,25*mm,30*mm,27*mm,38*mm]
    for pi,chunk in enumerate(chunks):
        story += [Paragraph('ROOM-WISE ATTENDANCE SHEET',title_style),Paragraph(f'Room: {room} | Date: {date_str} | Shift: {shift} | Total Students: {len(out)}',sub_style),Spacer(1,3*mm)]
        data=[[Paragraph(str(c),head) for c in out.columns]]
        for row in chunk.itertuples(index=False):
            data.append([Paragraph('' if pd.isna(v) else str(v),cell) for v in row])
        tab=Table(data,colWidths=widths,repeatRows=1)
        tab.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eef5')),('GRID',(0,0),(-1,-1),0.4,colors.grey),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(-1,0),'CENTER'),
            ('ALIGN',(0,0),(1,-1),'CENTER'),('ALIGN',(3,0),(5,-1),'CENTER'),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f8fafc')]),
            ('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)
        ]))
        story.append(tab)
        if pi<len(chunks)-1: story.append(PageBreak())
    doc.build(story)
    return buf.getvalue()

def pdf_course_allocation(df, course, date_str, shift):
    # Exact requested format: Sr. No | Name | Roll No | Seat No | Room No — Portrait A4.
    d=_add_seat_numbers(df)
    out=pd.DataFrame()
    out['Sr. No']=range(1,len(d)+1)
    out['Name']=d['Name'].astype(str) if 'Name' in d else ''
    out['Roll No']=d['Enrollment No'].apply(_roll) if 'Enrollment No' in d else ''
    out['Seat No']=d['Seat No'].astype(str) if 'Seat No' in d else ''
    out['Room No']=d['Room'].astype(str) if 'Room' in d else ''
    return pdf_table(f'COURSE-WISE ALLOCATION — {course}',f'Date: {date_str} | Shift: {shift} | Total Students: {len(out)}',out,landscape_mode=False,rows_per_page=28)

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

def apply_det(df, roll_col, name_col):
    if df.empty or det_master.empty or roll_col not in df.columns or name_col not in df.columns:
        return df.copy()
    out=df.copy()
    rolls=set(det_master['Roll No'].astype(str))
    hit=out[roll_col].apply(normalize_roll).isin(rolls)
    out.loc[hit,name_col]=(
        out.loc[hit,name_col].fillna('').astype(str)
        .str.replace(r'\s*\(det\)\s*$','',regex=True)
        .str.rstrip()+' (det)'
    )
    return out

# Apply DET marking to attendance/student records before filters and reports.
att=apply_det(att,'Enrollment No','Name')
sl=apply_det(sl,'Enrollment No','Name')
sp=apply_det(sp,'Enrollment No','Name')

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
        result[f"{_safe_filename(room)}_{_safe_filename(shift_value)}_{_safe_filename(date_value)}.pdf"]=pdf
    return result

def build_course_room_pdfs_for_date(date_value, shift_value, selected_courses=None):
    """Despite the historical function name, generate ONE course-wise allocation PDF per course."""
    d,sched=attendance_for_actual_papers(date_value,shift_value)
    if d.empty or 'Course' not in d.columns: return {}
    if selected_courses:
        d=d[d['Course'].astype(str).isin([str(x) for x in selected_courses])]
    result={}
    for course,rv in d.groupby('Course',dropna=False):
        course=str(course)
        pdf=pdf_course_allocation(rv,course,str(date_value),str(shift_value))
        result[f'{_safe_filename(course)}_{_safe_filename(shift_value)}_{_safe_filename(date_value)}.pdf']=pdf
    return result


tabs=st.tabs(['📊 Dashboard','🏫 Room-wise Attendance','📚 Course Count','👨‍🎓 Student Search','🪑 Seating','🗓️ Datesheet','📄 PDF Reports','📦 Bulk PDF Downloads','📝 DET Updates'])

with tabs[0]:
    st.subheader('Exam Operations Dashboard')
    if not att.empty:
        room_counts=af.groupby('Room').size().sort_values(ascending=False)
        st.markdown('**Students / attendance records by room**')
        st.bar_chart(room_counts)
        a,b=st.columns(2)
        with a:
            st.markdown('**Room summary**')
            st.dataframe(af.groupby(['Date','Shift','Room']).size().reset_index(name='Students'),use_container_width=True,hide_index=True)
        with b:
            st.markdown('**Course summary**')
            st.dataframe(af.groupby('Course').size().reset_index(name='Students').sort_values('Students',ascending=False),use_container_width=True,hide_index=True)

with tabs[1]:
    st.subheader('Room-wise Attendance Sheet')
    if af.empty: st.info('No attendance records for the selected filters.')
    else:
        room_view=af.copy()
        preview_cols=[c for c in ['S.No','Name','Enrollment No','Course','Answer Sheet No','Signature'] if c in room_view.columns]
        st.markdown('**Room PDF:** Sr. No | Seat No | Name | Roll No | Course | Answer Sheet No | Signature — Portrait A4')
        st.dataframe(room_view[preview_cols] if preview_cols else room_view,use_container_width=True,hide_index=True)
        csv=room_view.to_csv(index=False).encode('utf-8')
        st.download_button('⬇️ Download Room Attendance CSV',csv,'roomwise_attendance.csv','text/csv')
        if sel_room!='All':
            dstr=sel_date if sel_date!='All' else 'All Dates'; sh=sel_shift if sel_shift!='All' else 'All Shifts'
            st.download_button('📄 Generate Room Attendance PDF',pdf_room_attendance(room_view,sel_room,dstr,sh),f'{sel_room}_Attendance.pdf','application/pdf')
        else:
            st.info('Select a specific room in the sidebar to generate its dedicated PDF attendance sheet.')

with tabs[2]:
    st.subheader('Student Count of a Specific Course — Room-wise')
    source_df = af.copy()
    if source_df.empty:
        st.warning('No attendance/allocation data is available for the selected date/shift.')
    else:
        course_options = sorted(source_df['Course'].dropna().astype(str).unique().tolist())
        selected_course = st.selectbox('Select Course', course_options, key='course_room_count')
        cv = source_df[source_df['Course'].astype(str) == selected_course].copy()
        total = len(cv)
        room_summary = cv.groupby('Room', dropna=False).size().reset_index(name='Student Count').sort_values(
            ['Student Count','Room'], ascending=[False,True])
        a,b=st.columns(2)
        a.metric(f'Total {selected_course} students', total)
        b.metric('Rooms used', room_summary['Room'].nunique())
        st.markdown(f'### {selected_course} — Students in Each Room')
        st.dataframe(room_summary,use_container_width=True,hide_index=True)
        if not room_summary.empty:
            st.bar_chart(room_summary.set_index('Room')['Student Count'])
        if not sl.empty:
            check=sl.copy()
            if sel_date!='All': check=check[check['Date'].astype(str)==sel_date]
            if sel_shift!='All': check=check[check['Shift'].astype(str)==sel_shift]
            check=check[check['Course'].astype(str)==selected_course]
            if len(check)!=total:
                st.warning(f'Cross-check: course-wise student list has {len(check)} records, while room allocation has {total}. Review the source files.')
            else:
                st.success('Cross-check passed: course-wise student list and room allocation counts match.')
        st.download_button('⬇️ Download Course × Room Count CSV',room_summary.to_csv(index=False).encode('utf-8'),
                           f'{selected_course}_roomwise_count.csv','text/csv')

with tabs[3]:
    st.subheader('Student Search')
    if not sl.empty:
        q=st.text_input('Enrollment No / Student Name / Course / Room')
        v=sl.copy()
        if q:
            mask=v.astype(str).apply(lambda c:c.str.contains(q,case=False,na=False)).any(axis=1); v=v[mask]
        st.metric('Matching students',len(v))
        st.dataframe(v,use_container_width=True,hide_index=True)

with tabs[4]:
    st.subheader('Seating Plan')
    if not sp.empty:
        v=sp.copy()
        st.dataframe(v,use_container_width=True,hide_index=True)
    else: st.info('Seating workbook data was not detected.')

with tabs[5]:
    st.subheader('Class Test Datesheet')
    if datesheet.empty: st.info('Datesheet not detected.')
    else:
        v=datesheet.copy()
        q=st.text_input('Search paper code / paper name / program')
        if q:
            v=v[v.astype(str).apply(lambda c:c.str.contains(q,case=False,na=False)).any(axis=1)]
        st.dataframe(v,use_container_width=True,hide_index=True)
        st.download_button('⬇️ Download Datesheet CSV',v.to_csv(index=False).encode('utf-8'),'datesheet.csv','text/csv')

with tabs[6]:
    st.subheader('PDF Report Generator')
    report=st.selectbox('Report Type',['Room Attendance PDF (Portrait)','Course × Room Count PDF','Filtered Attendance PDF'])
    if report=='Room Attendance PDF':
        rr=st.selectbox('Room',rooms)
        rv=att[att['Room'].astype(str)==rr].copy()
        if sel_date!='All': rv=rv[rv['Date'].astype(str)==sel_date]
        if sel_shift!='All': rv=rv[rv['Shift'].astype(str)==sel_shift]
        st.write(f'**{rr}: {len(rv)} students**')
        st.download_button('📄 Generate PDF',pdf_room_attendance(rv,rr,sel_date,sel_shift),f'{rr}_Attendance.pdf','application/pdf')
    elif report=='Course Student Count PDF':
        if sl.empty: st.warning('No course data.')
        else:
            cc=st.selectbox('Course',sorted(sl['Course'].astype(str).unique()))
            cv=sl[sl['Course'].astype(str)==cc].copy()
            if sel_date!='All': cv=cv[cv['Date'].astype(str)==sel_date]
            if sel_shift!='All': cv=cv[cv['Shift'].astype(str)==sel_shift]
            st.write(f'**{cc}: {len(cv)} students**')
            cols=[c for c in ['S.No','Name','Enrollment No','Seat No','Room','Date','Shift','Course'] if c in cv.columns]
            st.download_button('📄 Generate PDF',pdf_course_summary(cv[cols],cc,sel_date,sel_shift),f'{cc}_Student_List.pdf','application/pdf')
    else:
        rv=af.copy(); st.write(f'Filtered records: **{len(rv)}**')
        st.download_button('📄 Generate PDF',pdf_table('Filtered Attendance Report',f'Date: {sel_date} | Shift: {sel_shift} | Room: {sel_room} | Course: {sel_course}',rv,True,26),'Filtered_Attendance.pdf','application/pdf')

st.sidebar.divider(); st.sidebar.caption(f'Loaded: {source}')


with tabs[8]:
    st.subheader('📝 DET Student Name Updates')
    st.write('Upload an Excel file containing Roll No. and Student Name. Matching Roll No. values are marked by appending **(det)** to the student name.')
    if det_master.empty:
        st.info('Upload the DET Excel file from the sidebar.')
    else:
        st.metric('Roll numbers in DET Excel',len(det_master))
        st.dataframe(det_master,use_container_width=True,hide_index=True)
        matched=att[att['Enrollment No'].apply(normalize_roll).isin(set(det_master['Roll No'].astype(str)))].copy() if not att.empty and 'Enrollment No' in att else pd.DataFrame()
        if not matched.empty:
            st.success(f'{len(matched)} attendance record(s) matched.')
            show=[c for c in ['Date','Shift','Room','S.No','Name','Enrollment No','Course','Answer Sheet No'] if c in matched.columns]
            st.dataframe(matched[show],use_container_width=True,hide_index=True)
            st.download_button('⬇️ Download DET-marked attendance CSV',matched.to_csv(index=False).encode('utf-8'),'det_marked_attendance.csv','text/csv')
        else:
            st.warning('No uploaded Roll No. matched the attendance records.')
        st.caption('The original ZIP is not modified. DET marking is applied only in the current app session.')


with tabs[7]:
    st.subheader("📦 Bulk PDF Downloads — Scheduled Papers Only")
    st.caption("Select a date and shift. The app checks the Class Test Datesheet and generates only eligible course-wise allocation PDFs and room-wise attendance PDFs for papers occurring at that time. All PDFs are Portrait A4.")

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
                        st.success(f"{len(files_dict)} course-room PDF(s) generated.")
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

