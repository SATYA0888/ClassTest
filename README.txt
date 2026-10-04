# ODD Minor Exam 2026 Interactive App v5

Run:
python -m pip install -r requirements.txt
python -m streamlit run app.py

v5 bulk PDF features:
1. Select an exam date and shift.
2. Generate one portrait PDF per room:
   ROOM_SHIFT_DATE.pdf
3. Generate one portrait PDF per course-room:
   COURSE_ROOM_SHIFT_DATE.pdf
4. Download all PDFs together as ZIP files.
5. Generate both room and course-room PDF sets in one click.
6. DET Excel upload and (det) marking retained.


v6: Bulk PDF downloads are schedule-aware. The app checks the Class Test Datesheet, maps shifts I-IV to the four time slots, and generates PDFs only for rooms/course groups whose paper is scheduled on the selected date and shift. The source workbook's date storage is normalized using its Validation sheet (05-09 Oct 2026).
