"""Combined PDTB + UCREL classroom quiz.
No password. SQLite is local to the Streamlit instance; use persistent shared DB for reliable cloud use.
"""
import sqlite3
import secrets
import time
from pathlib import Path

import streamlit as st
from questions import QUESTIONS

DB = Path(__file__).with_name("challenge.sqlite3")
st.set_page_config(page_title="PDTB + UCREL Pair Challenge", page_icon="📚", layout="wide")

def connect():
    con = sqlite3.connect(str(DB), timeout=20, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=20000")
    return con

def initialize():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS sessions (
            code TEXT PRIMARY KEY, topic TEXT NOT NULL, revealed INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS submissions (
            code TEXT NOT NULL, team TEXT NOT NULL, answers TEXT NOT NULL,
            submitted_at REAL NOT NULL, PRIMARY KEY(code, team))""")
initialize()

def get_session(code):
    with connect() as c:
        return c.execute("SELECT * FROM sessions WHERE code=?", (code,)).fetchone()

def all_submissions(code):
    with connect() as c:
        return c.execute("SELECT * FROM submissions WHERE code=? ORDER BY submitted_at", (code,)).fetchall()

def create_session(topic):
    for _ in range(10):
        code = secrets.token_hex(3).upper()
        try:
            with connect() as c:
                c.execute("INSERT INTO sessions(code,topic,created_at) VALUES(?,?,?)",
                          (code, topic, time.time()))
            return code
        except sqlite3.IntegrityError:
            continue
    raise RuntimeError("Unable to generate unique session code")

def save_answers(code,team,answers):
    import json
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        row=c.execute("SELECT revealed FROM sessions WHERE code=?", (code,)).fetchone()
        if row is None or row["revealed"]:
            c.execute("ROLLBACK")
            return False
        try:
            c.execute("INSERT INTO submissions(code,team,answers,submitted_at) VALUES(?,?,?,?)",
                      (code,team,json.dumps(answers),time.time()))
            c.execute("COMMIT")
            return True
        except sqlite3.IntegrityError:
            c.execute("ROLLBACK")
            return False

def score(qs, answers):
    return sum(a==q["answer"] for a,q in zip(answers,qs))

def results(code, topic):
    import json
    qs=QUESTIONS[topic]
    rows=[]
    for r in all_submissions(code):
        ans=json.loads(r["answers"])
        rows.append({"Team":r["team"],"Correct":score(qs,ans),
                     "Total":len(qs),"Submitted":time.strftime("%H:%M:%S",time.localtime(r["submitted_at"]))})
    return sorted(rows,key=lambda x:(-x["Correct"],x["Submitted"],x["Team"]))

st.title("📚 PDTB + UCREL Pair Challenge")
st.caption("Choose a discourse annotation topic. Each quiz has 20 questions. Results appear only after instructor reveal.")
role=st.radio("View",["Instructor","Team"],horizontal=True)

if role=="Instructor":
    st.subheader("Instructor dashboard")
    topic=st.selectbox("Create a new session for",["PDTB","UCREL"])
    if st.button("Create session",type="primary"):
        st.session_state["instructor_code"]=create_session(topic)
    code=st.text_input("Session code (created above or existing)",value=st.session_state.get("instructor_code","")).strip().upper()
    if code:
        s=get_session(code)
        if not s:
            st.error("Session not found.")
        else:
            st.info(f"Share code **{code}** with the teams. Topic: **{s['topic']}**.")
            @st.fragment(run_every="4s")
            def dashboard():
                current=get_session(code)
                if current is None:
                    st.warning("Session unavailable.")
                    return
                submissions=all_submissions(code)
                st.metric("Teams submitted",len(submissions))
                st.write("Submitted teams:",", ".join(r["team"] for r in submissions) or "None yet")
                if not current["revealed"]:
                    st.warning("Scores and correct answers are hidden.")
                    if st.button("Reveal results to all teams",key="reveal_"+code,type="primary"):
                        with connect() as c:
                            c.execute("UPDATE sessions SET revealed=1 WHERE code=?", (code,))
                        st.rerun()
                else:
                    st.success("Results revealed")
                    st.dataframe(results(code,current["topic"]),hide_index=True,use_container_width=True)
                    import csv,io
                    buf=io.StringIO()
                    writer=csv.DictWriter(buf,fieldnames=["Team","Correct","Total","Submitted"])
                    writer.writeheader();writer.writerows(results(code,current["topic"]))
                    st.download_button("Download scores (CSV)",buf.getvalue(),
                                       file_name=f"{current['topic']}_{code}_scores.csv",mime="text/csv")
                    with st.expander("Answer key and explanations"):
                        for i,q in enumerate(QUESTIONS[current["topic"]],1):
                            st.markdown(f"**{i}. {q['q']}**")
                            st.write(f"Answer: **{q['answer']}** — {q['why']}")
            dashboard()
    st.caption("No instructor password is used. Anyone with the instructor session code can reveal results. Do not use this version for high-stakes examinations.")
else:
    st.subheader("Team quiz")
    code=st.text_input("Enter the instructor's session code").strip().upper()
    team=st.text_input("Team name",placeholder="e.g., Team 1").strip()
    if code:
        s=get_session(code)
        if not s:
            st.error("Incorrect session code. Ask your instructor for the code.")
        else:
            topic=s["topic"]
            qs=QUESTIONS[topic]
            st.write(f"**Topic:** {topic} · **Questions:** {len(qs)}")
            existing={r["team"].casefold() for r in all_submissions(code)}
            submitted=bool(team and team.casefold() in existing)
            if submitted:
                st.info("This team name has already submitted for this session.")
            elif s["revealed"]:
                st.warning("Results have been revealed; new submissions are closed.")
            elif team:
                with st.form("quiz_"+code+"_"+team):
                    chosen=[]
                    for i,q in enumerate(qs,1):
                        st.markdown(f"**Q{i}. {q['q']}**")
                        chosen.append(st.radio("Select one",q["options"],index=None,
                                               key=f"{code}_{team}_{i}",label_visibility="collapsed"))
                    send=st.form_submit_button("Submit all answers",type="primary")
                    if send:
                        if any(a is None for a in chosen):
                            st.error("Please answer every question before submitting.")
                        elif save_answers(code,team,chosen):
                            st.success("Answers submitted. Wait for the instructor to reveal results.")
                            st.rerun()
                        else:
                            st.error("Submission was not accepted (team already submitted or results revealed).")
            @st.fragment(run_every="4s")
            def show_results():
                current=get_session(code)
                if current and current["revealed"]:
                    st.success("Instructor has revealed the results.")
                    st.dataframe(results(code,topic),hide_index=True,use_container_width=True)
                    with st.expander("All correct answers and explanations",expanded=True):
                        for i,q in enumerate(qs,1):
                            st.markdown(f"**Q{i}. {q['q']}**")
                            st.write(f"**Correct:** {q['answer']} — {q['why']}")
                elif submitted:
                    st.info("Waiting for instructor reveal… This page checks automatically.")
            show_results()
st.divider()
st.caption("Teaching illustrations, not official PDTB/UCREL gold annotations. Local SQLite requires one shared persistent Streamlit instance; cloud restarts may erase sessions.")
