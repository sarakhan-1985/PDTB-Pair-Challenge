# PDTB Pair Challenge

Run locally: `pip install -r requirements.txt` then `streamlit run app.py`.

1. Instructor selects Instructor, creates a competition, and shares the displayed code.
2. Six teams choose distinct names, join with the code, and complete 20 questions.
3. The instructor sees submission status. Scores and explanations stay hidden.
4. When all six teams submit, instructor clicks Reveal results. A close-round override is available.
5. Instructor downloads the CSV results and projects explanations.

## Important deployment limitations
This is a password-free classroom prototype. Anyone who selects Instructor can create or reveal sessions, and a team name is not identity-verified. The SQLite database is stored on the app server. It works for multiple browsers **when they reach the same persistent server instance**. Streamlit Community Cloud may restart or replace local storage, and multi-instance hosting will not synchronize SQLite files. For reliable hosted competitions, use a managed shared database (e.g., Supabase/Postgres), restrict instructor access, and add team authentication. Test with multiple devices before class.

## Annotation scope
The questions teach introductory PDTB-style discourse relations, with simplified examples of explicit/implicit relations, Arg1/Arg2 and four top-level PDTB 3.0 senses. They are not a substitute for official PDTB annotation guidelines or exhaustive sense inventories. Some natural-language examples admit multiple readings; the questions specify the intended interpretation when needed.
