import os
import secrets
import sqlite3
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from questions import QUESTIONS

st.set_page_config(page_title='PDTB Pair Challenge', page_icon='🏆', layout='wide')
DB_PATH = os.getenv('PDTB_DB_PATH', 'pdtb_challenge.sqlite3')
TEAM_LIMIT = 6

def conn():
    c=sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA busy_timeout=30000')
    return c

def init():
    with conn() as c:
        c.execute('CREATE TABLE IF NOT EXISTS sessions(code TEXT PRIMARY KEY, status TEXT NOT NULL, created_at TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS teams(code TEXT NOT NULL, name TEXT NOT NULL, submitted INTEGER NOT NULL DEFAULT 0, answers TEXT NOT NULL DEFAULT "{}", PRIMARY KEY(code,name))')
init()

def session(code):
    with conn() as c:
        return c.execute('SELECT status FROM sessions WHERE code=?',(code,)).fetchone()

def teams(code):
    with conn() as c:
        return c.execute('SELECT name,submitted,answers FROM teams WHERE code=? ORDER BY name',(code,)).fetchall()

def score(answer_map):
    return sum(answer_map.get(str(i)) == q[3] for i,q in enumerate(QUESTIONS))

def store_answers(code,name,answer_map,submit=False):
    import json
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        s=c.execute('SELECT status FROM sessions WHERE code=?',(code,)).fetchone()
        t=c.execute('SELECT submitted FROM teams WHERE code=? AND name=?',(code,name)).fetchone()
        if not s or s[0]!='open' or not t or t[0]:
            c.execute('ROLLBACK'); return False
        c.execute('UPDATE teams SET answers=?, submitted=? WHERE code=? AND name=?',(json.dumps(answer_map),int(submit),code,name))
        c.execute('COMMIT')
    return True

st.title('🏆 PDTB Discourse Annotation Pair Challenge')
st.caption('Six teams · 20 questions · PDTB discourse relations · Instructor-controlled result reveal')
st.info('Classroom version: no instructor password. Anyone with the link can access Instructor controls. Use only in a trusted class.')
role=st.sidebar.radio('Access', ['Team','Instructor'])

if role=='Instructor':
    st.subheader('Instructor dashboard')
    if st.button('Create a new competition',type='primary'):
        with conn() as c:
            while True:
                code='PDTB'+str(secrets.randbelow(9000)+1000)
                try:
                    c.execute('INSERT INTO sessions VALUES (?,?,?)',(code,'open',datetime.now(timezone.utc).isoformat()))
                    break
                except sqlite3.IntegrityError: pass
        st.session_state['instructor_code']=code
    code=st.text_input('Session code (create or paste existing)',value=st.session_state.get('instructor_code','')).strip().upper()
    if code:
        st.session_state['instructor_code']=code
        s=session(code)
        if not s: st.error('Session not found. Create a new competition first.')
        else:
            rows=teams(code)
            submitted=sum(r[1] for r in rows)
            st.metric('Teams submitted',f'{submitted}/{TEAM_LIMIT}')
            st.write('Session code to share with teams: **'+code+'**')
            st.write('Status: **'+s[0].upper()+'**')
            st.dataframe(pd.DataFrame([{'Team':r[0],'Status':'Submitted' if r[1] else 'Working'} for r in rows]),hide_index=True,use_container_width=True)
            if s[0]=='open':
                if st.button('Reveal results',disabled=not(len(rows)==TEAM_LIMIT and submitted==TEAM_LIMIT)):
                    with conn() as c: c.execute('UPDATE sessions SET status="revealed" WHERE code=? AND status="open"',(code,))
                    st.rerun()
                if st.button('Close round and reveal (unanswered = incorrect)'):
                    with conn() as c: c.execute('UPDATE sessions SET status="revealed" WHERE code=? AND status="open"',(code,))
                    st.rerun()
                st.caption('Normal Reveal Results unlocks only after all six teams submit. The close-round option is for absences or incomplete teams.')
            if s[0]=='revealed':
                import json
                result=sorted([{'Team':r[0],'Correct':score(json.loads(r[2])),'Total':len(QUESTIONS)} for r in rows],key=lambda x:(-x['Correct'],x['Team']))
                st.subheader('🏅 Leaderboard')
                st.dataframe(pd.DataFrame(result),hide_index=True,use_container_width=True)
                st.download_button('Download results (CSV)',pd.DataFrame(result).to_csv(index=False),'pdtb_scores.csv','text/csv')
                st.subheader('Question-by-question explanations')
                for i,(sent,question,options,correct,explanation) in enumerate(QUESTIONS,1):
                    with st.expander(f'Question {i}: {question}'):
                        st.write('**Sentence:**',sent)
                        st.success('Correct answer: '+options[correct])
                        st.write(explanation)
            st.button('Refresh dashboard',on_click=lambda:None)
else:
    st.subheader('Team participation')
    code=st.text_input('Session code').strip().upper()
    name=st.selectbox('Team name',[f'Team {x}' for x in 'ABCDEF'])
    if st.button('Join or resume',type='primary'):
        s=session(code)
        if not s: st.error('Incorrect session code. Ask your instructor for the current code.')
        else:
            with conn() as c:
                c.execute('INSERT OR IGNORE INTO teams(code,name) VALUES (?,?)',(code,name))
            st.session_state['joined']=(code,name)
    joined=st.session_state.get('joined')
    if joined:
        code,name=joined
        s=session(code)
        row=next((r for r in teams(code) if r[0]==name),None)
        if not s or not row: st.error('Session or team unavailable.')
        else:
            import json
            saved=json.loads(row[2]); st.write(f'**{name}** · Session **{code}**')
            if s[0]=='revealed':
                st.success('The instructor has revealed the results.')
                st.metric('Your score',f'{score(saved)}/{len(QUESTIONS)}')
                for i,(sent,question,options,correct,explanation) in enumerate(QUESTIONS):
                    with st.expander(f'Question {i+1}: {question}'):
                        st.write(sent)
                        chosen=saved.get(str(i))
                        st.write('Your answer:',options[chosen] if isinstance(chosen,int) and 0<=chosen<len(options) else 'Not answered')
                        st.write('Correct answer:',options[correct]); st.write(explanation)
            elif row[1]:
                st.success('Answers submitted. Scores and explanations will appear only when the instructor reveals them.')
                st.button('Check for revealed results',on_click=lambda:None)
            else:
                st.caption('Discuss answers with your teammate. No feedback is shown during the quiz.')
                with st.form('quiz'):
                    answers={}
                    for i,(sent,question,options,correct,explanation) in enumerate(QUESTIONS):
                        st.markdown(f'**Q{i+1}. {question}**')
                        st.write(sent)
                        current=saved.get(str(i),-1)
                        pick=st.radio('Select an answer',range(-1,len(options)),format_func=lambda j:'— Select —' if j==-1 else options[j],index=current+1 if current>=0 else 0,key=f'ans_{code}_{name}_{i}')
                        if pick>=0: answers[str(i)]=pick
                    col1,col2=st.columns(2)
                    with col1: save=st.form_submit_button('Save progress')
                    with col2: submit=st.form_submit_button('Submit final answers',type='primary')
                if save or submit:
                    if store_answers(code,name,answers,submit=submit):
                        st.success('Submitted!' if submit else 'Progress saved.')
                        st.rerun()
                    else: st.warning('The session is no longer accepting answers. Refresh to check results.')
