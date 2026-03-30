import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import pandas as pd
import os
import json

# ========== CONFIGURAZIONE PAGINA ==========
st.set_page_config(page_title="Rocket Scrim", page_icon="🏎️", layout="wide")

# ========== FIREBASE ==========
def init_firebase():
    """Inizializza Firebase usando variabile d'ambiente o file locale"""
    # Prova a leggere dalla variabile d'ambiente (Render)
    firebase_key_json = os.environ.get('FIREBASE_KEY')
    
    if firebase_key_json:
        try:
            cred_dict = json.loads(firebase_key_json)
            cred = credentials.Certificate(cred_dict)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            return firestore.client()
        except Exception as e:
            st.error(f"❌ Errore Firebase (variabile): {e}")
            return None
    
    # Se non c'è variabile, prova con file locale (per test)
    for f in os.listdir('.'):
        if f.endswith('.json') and f != 'dati_locali.json':
            try:
                cred = credentials.Certificate(f)
                if not firebase_admin._apps:
                    firebase_admin.initialize_app(cred)
                return firestore.client()
            except:
                pass
    
    st.error("❌ Firebase non configurato! Contatta l'amministratore.")
    return None

db = init_firebase()
if db is None:
    st.stop()

# ========== DATI ==========
ALL_RANKS = ["Bronzo 1", "Bronzo 2", "Bronzo 3", "Argento 1", "Argento 2", "Argento 3",
             "Oro 1", "Oro 2", "Oro 3", "Platino 1", "Platino 2", "Platino 3",
             "Diamante 1", "Diamante 2", "Diamante 3", "Champion 1", "Champion 2", "Champion 3",
             "Grand Champion 1", "Grand Champion 2", "Grand Champion 3", "Super Sonic Legend"]

FORMATI = ["1v1", "2v2", "3v3"]
SERVER = ["EU", "NA", "SA", "AS", "OCE", "ME"]

def mmr_da_rank(rank):
    valori = {"Bronzo 1": 100, "Bronzo 2": 150, "Bronzo 3": 200, "Argento 1": 250, "Argento 2": 300, "Argento 3": 350,
              "Oro 1": 400, "Oro 2": 450, "Oro 3": 500, "Platino 1": 550, "Platino 2": 600, "Platino 3": 650,
              "Diamante 1": 700, "Diamante 2": 750, "Diamante 3": 800, "Champion 1": 850, "Champion 2": 900, "Champion 3": 950,
              "Grand Champion 1": 1000, "Grand Champion 2": 1050, "Grand Champion 3": 1100, "Super Sonic Legend": 1200}
    return valori.get(rank, 500)

# ========== SESSION STATE ==========
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.user_id = None

# ========== FUNZIONI ==========
def login(email, password):
    users = list(db.collection('users').where('email', '==', email).where('password', '==', password).stream())
    if users:
        st.session_state.logged_in = True
        st.session_state.user = email
        st.session_state.user_id = users[0].id
        return True
    return False

def register(email, password):
    existing = list(db.collection('users').where('email', '==', email).stream())
    if existing:
        return False
    db.collection('users').add({"email": email, "password": password, "created_at": datetime.now().isoformat()})
    return True

def get_my_teams():
    return list(db.collection('teams').where('members', 'array_contains', st.session_state.user_id).stream())

def get_all_scrims():
    return list(db.collection('scrims').stream())

def create_team(name, rank):
    db.collection('teams').add({
        "name": name, "rank": rank, "mmr": mmr_da_rank(rank),
        "wins": 0, "losses": 0, "goals_scored": 0, "goals_conceded": 0,
        "owner": st.session_state.user_id, "members": [st.session_state.user_id],
        "created_at": datetime.now().isoformat()
    })

def create_scrim(team_id, team_name, opponent, formato, server, rank_min, rank_max, date_time):
    db.collection('scrims').add({
        "my_team_id": team_id, "my_team_name": team_name, "organizzatore": team_name,
        "opponent_team_id": opponent if opponent else "APERTA", "formato": formato, "server": server,
        "rank_min": rank_min, "rank_max": rank_max, "creatore_uid": st.session_state.user_id,
        "status": "pending", "date": date_time.isoformat(), "created_at": datetime.now().isoformat()
    })

def delete_scrim(scrim_id):
    db.collection('scrims').document(scrim_id).delete()

def delete_team(team_id):
    db.collection('teams').document(team_id).delete()

def update_scrim_time(scrim_id, new_date):
    db.collection('scrims').document(scrim_id).update({"date": new_date.isoformat()})

def register_result(scrim_id, winner_id, loser_id, goal_w, goal_l):
    db.collection('scrims').document(scrim_id).update({"status": "completed", "result": f"{goal_w}-{goal_l}"})
    if winner_id and winner_id != "APERTA":
        team_ref = db.collection('teams').document(winner_id)
        team = team_ref.get().to_dict()
        if team:
            new_mmr = team.get('mmr', 500) + 25 + (goal_w - goal_l)
            team_ref.update({"mmr": new_mmr, "wins": firestore.Increment(1), "goals_scored": firestore.Increment(goal_w), "goals_conceded": firestore.Increment(goal_l)})
    if loser_id and loser_id != "APERTA":
        team_ref = db.collection('teams').document(loser_id)
        team = team_ref.get().to_dict()
        if team:
            new_mmr = max(0, team.get('mmr', 500) - 25 - (goal_l - goal_w))
            team_ref.update({"mmr": new_mmr, "losses": firestore.Increment(1), "goals_scored": firestore.Increment(goal_l), "goals_conceded": firestore.Increment(goal_w)})

def join_scrim(scrim_id, team_name):
    db.collection('scrims').document(scrim_id).update({"opponent_team_id": team_name, "opponent_uid": st.session_state.user_id})

# ========== UI ==========
if not st.session_state.logged_in:
    st.title("🏎️ ROCKET SCRIM")
    st.markdown("### 🌐 Organizza scrim con la tua community")
    
    tab1, tab2 = st.tabs(["🔐 ACCEDI", "📝 REGISTRATI"])
    
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Accedi", use_container_width=True):
            if login(email, password):
                st.rerun()
            else:
                st.error("Email o password errati")
    
    with tab2:
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_pass")
        if st.button("Registrati", use_container_width=True):
            if register(email, password):
                st.success("Registrato! Ora accedi")
            else:
                st.error("Email già esistente")
else:
    st.sidebar.title(f"👋 {st.session_state.user}")
    st.sidebar.markdown("---")
    
    menu = st.sidebar.radio("MENU", ["🏠 HOME", "⚔️ SCRIM", "🏆 CLASSIFICA", "📊 STATISTICHE", "🚪 LOGOUT"])
    
    if menu == "🚪 LOGOUT":
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.user_id = None
        st.rerun()
    
    # Carica dati
    my_teams = get_my_teams()
    all_scrims = get_all_scrims()
    all_scrims.sort(key=lambda x: x.to_dict().get('date', ''), reverse=True)
    
    if menu == "🏠 HOME":
        st.title("🏠 HOME")
        
        # Statistiche
        col1, col2, col3 = st.columns(3)
        total_wins = sum(t.to_dict().get('wins', 0) for t in my_teams)
        total_losses = sum(t.to_dict().get('losses', 0) for t in my_teams)
        avg_mmr = sum(t.to_dict().get('mmr', 500) for t in my_teams) // len(my_teams) if my_teams else 0
        col1.metric("🏆 VITTORIE", total_wins)
        col2.metric("💔 SCONFITTE", total_losses)
        col3.metric("📊 MMR MEDIO", avg_mmr)
        
        st.divider()
        
        # Crea Team
        with st.expander("➕ CREA NUOVO TEAM", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                team_name = st.text_input("Nome team")
            with col2:
                team_rank = st.selectbox("Rank", ALL_RANKS)
            if st.button("Crea Team", use_container_width=True):
                if team_name:
                    create_team(team_name, team_rank)
                    st.success(f"Team {team_name} creato!")
                    st.rerun()
                else:
                    st.error("Inserisci un nome")
        
        st.divider()
        
        # I miei team
        st.subheader("📋 I MIEI TEAM")
        if my_teams:
            for team in my_teams:
                t = team.to_dict()
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                col1.write(f"**{t['name']}**")
                col2.write(f"{t['rank']} | MMR: {t['mmr']}")
                col3.write(f"V:{t['wins']} S:{t['losses']}")
                if col4.button("🗑️", key=f"del_team_{team.id}"):
                    delete_team(team.id)
                    st.rerun()
        else:
            st.info("Nessun team. Creane uno!")
        
        st.divider()
        
        # Crea Scrim
        with st.expander("⚔️ CREA NUOVA SCRIM", expanded=False):
            if my_teams:
                col1, col2 = st.columns(2)
                with col1:
                    team_options = [t.to_dict()['name'] for t in my_teams]
                    selected_team = st.selectbox("Il tuo team", team_options)
                    opponent = st.text_input("Team avversario (vuoto=APERTA)")
                    formato = st.selectbox("Formato", FORMATI)
                    server = st.selectbox("Server", SERVER)
                with col2:
                    rank_min = st.selectbox("Rank minimo avversario", ["Qualsiasi"] + ALL_RANKS)
                    rank_max = st.selectbox("Rank massimo avversario", ["Qualsiasi"] + ALL_RANKS)
                    date = st.date_input("Data", min_value=datetime.now().date())
                    time = st.time_input("Ora", datetime.now().time())
                
                if st.button("Crea Scrim", use_container_width=True):
                    date_time = datetime.combine(date, time)
                    team_obj = next(t for t in my_teams if t.to_dict()['name'] == selected_team)
                    create_scrim(team_obj.id, selected_team, opponent, formato, server, 
                                rank_min if rank_min != "Qualsiasi" else None, 
                                rank_max if rank_max != "Qualsiasi" else None, date_time)
                    st.success("Scrim creata!")
                    st.rerun()
            else:
                st.warning("Crea prima un team")
    
    elif menu == "⚔️ SCRIM":
        st.title("⚔️ SCRIM DISPONIBILI")
        st.caption(f"Totale: {len(all_scrims)}")
        
        if all_scrims:
            for doc in all_scrims:
                s = doc.to_dict()
                is_mia = s.get('creatore_uid') == st.session_state.user_id
                data_ora = datetime.fromisoformat(s.get('date', datetime.now().isoformat()))
                
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                    with col1:
                        st.write(f"**🏠 {s.get('organizzatore', '?')}**")
                        st.write(f"Vs: {s.get('opponent_team_id', 'APERTA')}")
                    with col2:
                        st.write(f"{s.get('formato', '3v3')} | {s.get('server', 'EU')}")
                        if s.get('rank_min') and s.get('rank_max'):
                            st.write(f"🎯 Rank: {s.get('rank_min')}→{s.get('rank_max')}")
                    with col3:
                        st.write(f"📅 {data_ora.strftime('%d/%m/%Y %H:%M')}")
                        st.write(f"Stato: {s.get('status', 'pending')}")
                    with col4:
                        if is_mia:
                            if st.button("✏️", key=f"edit_{doc.id}"):
                                new_date = st.date_input("Nuova data", value=data_ora.date(), key=f"date_{doc.id}")
                                new_time = st.time_input("Nuova ora", value=data_ora.time(), key=f"time_{doc.id}")
                                if st.button("Salva", key=f"save_{doc.id}"):
                                    update_scrim_time(doc.id, datetime.combine(new_date, new_time))
                                    st.rerun()
                            if st.button("📊", key=f"result_{doc.id}"):
                                goal1 = st.number_input(f"Goal {s.get('my_team_name')}", 0, 20, key=f"g1_{doc.id}")
                                goal2 = st.number_input(f"Goal {s.get('opponent_team_id')}", 0, 20, key=f"g2_{doc.id}")
                                if st.button("Conferma", key=f"conf_{doc.id}"):
                                    if goal1 > goal2:
                                        register_result(doc.id, s.get('my_team_id'), s.get('opponent_team_id'), goal1, goal2)
                                    elif goal2 > goal1:
                                        register_result(doc.id, s.get('opponent_team_id'), s.get('my_team_id'), goal2, goal1)
                                    st.rerun()
                            if st.button("🗑️", key=f"del_scrim_{doc.id}"):
                                delete_scrim(doc.id)
                                st.rerun()
                        else:
                            if s.get('status') == 'pending':
                                if st.button("🎮 PARTECIPA", key=f"join_{doc.id}"):
                                    if my_teams:
                                        team_name = st.selectbox("Scegli il tuo team", [t.to_dict()['name'] for t in my_teams], key=f"team_{doc.id}")
                                        if st.button("Conferma", key=f"join_confirm_{doc.id}"):
                                            join_scrim(doc.id, team_name)
                                            st.rerun()
                                    else:
                                        st.warning("Crea prima un team")
                    st.divider()
        else:
            st.info("Nessuna scrim disponibile")
    
    elif menu == "🏆 CLASSIFICA":
        st.title("🏆 CLASSIFICA MMR")
        
        all_teams = list(db.collection('teams').stream())
        classifica = []
        for doc in all_teams:
            t = doc.to_dict()
            classifica.append({"name": t.get('name', '?'), "mmr": t.get('mmr', 500), "wins": t.get('wins', 0), "losses": t.get('losses', 0)})
        classifica.sort(key=lambda x: x['mmr'], reverse=True)
        
        df = pd.DataFrame(classifica[:20])
        df.index = range(1, len(df) + 1)
        st.dataframe(df, use_container_width=True)
    
    elif menu == "📊 STATISTICHE":
        st.title("📊 STATISTICHE TEAM")
        
        if my_teams:
            for team in my_teams:
                t = team.to_dict()
                total = t.get('wins', 0) + t.get('losses', 0)
                winrate = (t.get('wins', 0) / total * 100) if total > 0 else 0
                diff = t.get('goals_scored', 0) - t.get('goals_conceded', 0)
                
                with st.expander(f"🏆 {t['name']}"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Rank", t.get('rank', 'N/D'))
                    col1.metric("MMR", t.get('mmr', 500))
                    col2.metric("Vittorie", t.get('wins', 0))
                    col2.metric("Sconfitte", t.get('losses', 0))
                    col3.metric("Winrate", f"{winrate:.1f}%")
                    col3.metric("Differenza Goal", f"{diff:+d}", delta_color="normal")
        else:
            st.info("Nessun team")