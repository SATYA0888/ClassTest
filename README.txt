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
   # ODD Minor Exam Interactive Management System

Bulk PDF output: course-wise allocation and room-wise attendance, portrait A4, filtered by actual scheduled paper/date/shift.
# ODD Minor Exam Interactive Management System

Bulk PDF output: course-wise allocation and room-wise attendance, portrait A4, filtered by actual scheduled paper/date/shift.


v12: All generated PDFs are forced to A4 portrait only. No landscape or non-A4 page sizes are used.


v13: Fixed blank PDF generation by normalizing PDF input columns and using the actual filtered dataframe rows. Empty datasets are skipped. Course-wise PDFs are generated one populated PDF per course.


v14: Fixed NameError caused by undefined tabs[7]. Bulk PDF section now runs at top level without requiring a missing tabs object.

