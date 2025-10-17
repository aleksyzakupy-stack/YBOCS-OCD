import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import pandas as pd
from datetime import datetime, date
import json
from pathlib import Path
import matplotlib.pyplot as plt

APP_TITLE = "Ocena nasilenia OCD – Y‑BOCS (PL)"
DATA_DIR = Path("data")
USER_STORE = DATA_DIR / "users"
RESULTS_FILE = DATA_DIR / "wyniki.csv"

st.set_page_config(page_title=APP_TITLE, page_icon="🧠", layout="wide")

# ---------- Helpers ----------
def ensure_dirs():
    DATA_DIR.mkdir(exist_ok=True)
    USER_STORE.mkdir(parents=True, exist_ok=True)

def load_credentials():
    with open("users.yaml", "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=SafeLoader)
    return config


def save_credentials(config: dict):
    with open("users.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)


def register_user_ui(config: dict, authenticator: stauth.Authenticate):
    st.subheader("Rejestracja użytkownika")
    st.caption("Podaj imię, trzy pierwsze litery nazwiska, unikalny login oraz hasło.")

    with st.form("register_form"):
        first_name = st.text_input("Imię", max_chars=50)
        surname_letters = st.text_input("Pierwsze trzy litery nazwiska", max_chars=3)
        login = st.text_input("Login", max_chars=32)
        password = st.text_input("Hasło", type="password")
        password_repeat = st.text_input("Powtórz hasło", type="password")
        submitted = st.form_submit_button("Zarejestruj")

    if not submitted:
        return

    errors = []
    first_name_clean = first_name.strip()
    letters_clean = surname_letters.strip().replace(" ", "")
    login_clean = login.strip()

    if not first_name_clean:
        errors.append("Imię jest wymagane.")
    if len(letters_clean) != 3 or not letters_clean.isalpha():
        errors.append("Podaj dokładnie trzy litery nazwiska (bez znaków specjalnych).")
    if not login_clean:
        errors.append("Login jest wymagany.")
    elif login_clean in config['credentials']['usernames']:
        errors.append("Taki login już istnieje.")
    if not password:
        errors.append("Hasło jest wymagane.")
    elif password != password_repeat:
        errors.append("Hasła muszą być identyczne.")

    if errors:
        for err in errors:
            st.error(err)
        return

    display_name = f"{first_name_clean.title()} {letters_clean.upper()}"
    hashed_password = stauth.Hasher([password]).generate()[0]

    config['credentials']['usernames'][login_clean] = {
        "email": f"{login_clean}@example.com",
        "name": display_name,
        "password": hashed_password,
        "role": "user",
    }

    save_credentials(config)
    if hasattr(authenticator, "credentials"):
        authenticator.credentials = config['credentials']

    st.success("Konto zostało utworzone. Możesz się teraz zalogować.")
    st.session_state["just_registered_user"] = login_clean
    st.experimental_rerun()

def get_user_dir(username: str) -> Path:
    d = USER_STORE / username
    d.mkdir(parents=True, exist_ok=True)
    return d

def user_symptoms_file(username: str) -> Path:
    return get_user_dir(username) / "objawy.json"

def load_user_symptoms(username: str) -> list:
    fp = user_symptoms_file(username)
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_user_symptoms(username: str, symptoms: list):
    user_symptoms_file(username).write_text(json.dumps(symptoms, ensure_ascii=False, indent=2), encoding="utf-8")

def init_results_file():
    if not RESULTS_FILE.exists():
        df = pd.DataFrame(columns=[
            "timestamp","date","user","role","objaw","q1","q2","q3","q4","q5","q6","q7","q8","q9","q10","suma"
        ])
        df.to_csv(RESULTS_FILE, index=False, encoding="utf-8")

def append_result(row: dict):
    init_results_file()
    df = pd.read_csv(RESULTS_FILE, dtype=str, keep_default_na=False, encoding="utf-8")
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(RESULTS_FILE, index=False, encoding="utf-8")

def load_results() -> pd.DataFrame:
    init_results_file()
    df = pd.read_csv(RESULTS_FILE, encoding="utf-8")
    # fix dtypes
    for q in ["q1","q2","q3","q4","q5","q6","q7","q8","q9","q10","suma"]:
        if q in df.columns:
            df[q] = pd.to_numeric(df[q], errors="coerce")
    return df

# ---------- Domain: list of symptoms (Polish) ----------
SYMPTOMS = {
    "Obsesje agresywne": [
        "Lęk, że może skrzywdzić siebie",
        "Lęk, że może skrzywdzić innych",
        "Obrazy przemocy lub okrucieństwa",
        "Lęk przed wypowiedzeniem obscenicznych słów lub obelg",
        "Lęk przed zrobieniem czegoś kompromitującego",
        "Lęk, że zrealizuje niechciane impulsy (np. dźgnięcie przyjaciela)",
        "Lęk, że coś ukradnie",
        "Lęk, że skrzywdzi innych przez nieuwagę (np. potrąci kogoś i odjedzie)",
        "Lęk, że będzie odpowiedzialny za nieszczęście (np. pożar, włamanie)",
        "Inne (dopisz w polu poniżej)"
    ],
    "Obsesje kontaminacyjne (zanieczyszczenia)": [
        "Obrzydzenie dot. wydzielin ciała (mocz, kał, ślina)",
        "Lęk przed brudem lub zarazkami",
        "Nadmierny lęk przed zanieczyszczeniami środowiskowymi",
        "Nadmierny lęk przed środkami domowymi (detergenty, rozpuszczalniki)",
        "Nadmierny lęk przed zwierzętami (np. owady)",
        "Niepokój przy kontakcie z lepkimi substancjami",
        "Lęk, że zachoruje przez kontakt z zanieczyszczeniem",
        "Lęk, że zarazi innych przez rozprzestrzenienie zanieczyszczenia",
        "Brak lęku dot. konsekwencji poza samym uczuciem nieczystości",
        "Inne (dopisz w polu poniżej)"
    ],
    "Obsesje seksualne": [
        "Zakazane/dewiacyjne treści seksualne (myśli/obrazy/impulsy)",
        "Treści dotyczące dzieci lub kazirodztwa",
        "Treści dotyczące homoseksualizmu",
        "Myśli o zachowaniach seksualnych wobec innych",
        "Inne (dopisz w polu poniżej)"
    ],
    "Obsesje somatyczne i gromadzenie": [
        "Lęk przed chorobą",
        "Nadmierna troska o wygląd/część ciała (dysmorfofobia)",
        "Potrzeba gromadzenia/oszczędzania",
        "Inne (dopisz w polu poniżej)"
    ],
    "Kompulsje czyszczenia/mycia": [
        "Nadmierne/zrytualizowane mycie rąk",
        "Nadmierne/zrytualizowane kąpiele, higiena, toaleta",
        "Czyszczenie przedmiotów/innych rzeczy",
        "Unikanie/środki by nie mieć kontaktu z zanieczyszczeniami",
        "Inne (dopisz w polu poniżej)"
    ],
    "Kompulsje sprawdzania": [
        "Sprawdzanie zamków, kuchenki, urządzeń",
        "Czy nie skrzywdził/nie skrzywdzi innych",
        "Czy nie skrzywdził/nie skrzywdzi siebie",
        "Czy nie wydarzyło się/nie wydarzy się coś strasznego",
        "Czy nie popełnił błędu",
        "Sprawdzanie związane z obsesjami somatycznymi",
        "Inne (dopisz w polu poniżej)"
    ],
    "Rytyny powtarzania/liczenia/porządkowania": [
        "Ponowne czytanie lub przepisywanie",
        "Powtarzanie czynności rutynowych",
        "Liczenie",
        "Porządkowanie/układanie",
        "Inne (dopisz w polu poniżej)"
    ],
    "Obsesje religijne/symetria/inne": [
        "Lęk przed świętokradztwem i bluźnierstwem",
        "Nadmierny niepokój moralny",
        "Potrzeba symetrii/dokładności z myśleniem magicznym",
        "Potrzeba symetrii/dokładności bez myślenia magicznego",
        "Potrzeba wiedzieć/pamiętać, lęk przed zgubieniem rzeczy",
        "Natrętne obrazy, dźwięki, słowa, melodie",
        "Drażliwość na dźwięki, liczby, kolory, przesądy",
        "Inne (dopisz w polu poniżej)"
    ],
    "Kompulsje różne": [
        "Rytuały umysłowe",
        "Nadmierne sporządzanie list",
        "Potrzeba mówienia/pytania/wyznawania",
        "Potrzeba dotykania/stukania/pocierania",
        "Rytuały mrugania/wpatrywania",
        "Środki zapobiegawcze (krzywda sobie/innym/katastrofa – nie sprawdzanie)",
        "Zrytualizowane zachowania przy jedzeniu",
        "Zachowania przesądne",
        "Trichotillomania",
        "Inne zachowania samouszkadzające",
        "Inne (dopisz w polu poniżej)"
    ]
}

# Y-BOCS items (Polish)
YBOCS_ITEMS = [
    ("Czas zajmowany przez myśli natrętne", [
        "Brak",
        "Mniej niż 1 godz./dobę lub sporadycznie",
        "1–3 godz./dobę lub często",
        "Ponad 3 do 8 godz./dobę lub bardzo często",
        "Ponad 8 godz./dobę lub prawie stale",
    ]),
    ("Interferencja z powodu myśli natrętnych", [
        "Brak",
        "Niewielka – funkcjonowanie zasadniczo nieupośledzone",
        "Wyraźna – ale da się funkcjonować",
        "Znaczne upośledzenie funkcjonowania",
        "Uniemożliwia funkcjonowanie",
    ]),
    ("Distress związany z myślami natrętnymi", [
        "Brak",
        "Niewielki – mało dokuczliwy",
        "Dokuczliwy, ale do opanowania",
        "Bardzo dokuczliwy",
        "Prawie stały i obezwładniający",
    ]),
    ("Opór wobec obsesji (wysiłek, by się im oprzeć)", [
        "Zawsze stara się opierać",
        "Najczęściej stara się opierać",
        "Czasem podejmuje wysiłek",
        "Ulega wszystkim obsesjom, z pewną niechęcią",
        "Całkowicie i chętnie ulega obsesjom",
    ]),
    ("Kontrola nad myślami natrętnymi", [
        "Pełna kontrola",
        "Zwykle potrafi zatrzymać/przełączyć myśli",
        "Czasem potrafi zatrzymać/przełączyć",
        "Rzadko skuteczny, z trudem",
        "Brak kontroli, myśli całkowicie mimowolne",
    ]),
    ("Czas poświęcony kompulsjom", [
        "Brak",
        "Mniej niż 1 godz./dobę lub sporadycznie",
        "1–3 godz./dobę lub często",
        "Ponad 3 do 8 godz./dobę lub bardzo często",
        "Ponad 8 godz./dobę lub prawie stale",
    ]),
    ("Interferencja z powodu kompulsji", [
        "Brak",
        "Niewielka – funkcjonowanie zasadniczo nieupośledzone",
        "Wyraźna – ale do opanowania",
        "Znaczne upośledzenie funkcjonowania",
        "Uniemożliwia funkcjonowanie",
    ]),
    ("Distress przy przerwaniu kompulsji", [
        "Brak",
        "Niewielki – przy lekkim ograniczeniu",
        "Narasta, ale do opanowania",
        "Znaczny i bardzo dokuczliwy",
        "Obezwładniający lęk",
    ]),
    ("Opór wobec kompulsji", [
        "Zawsze próbuje się opierać",
        "Najczęściej próbuje się opierać",
        "Czasem podejmuje wysiłek",
        "Ulega prawie wszystkim kompulsjom z niechęcią",
        "Całkowicie i chętnie ulega kompulsjom",
    ]),
    ("Kontrola nad kompulsjami", [
        "Pełna kontrola",
        "Presja, ale zwykle potrafi kontrolować",
        "Silna presja, kontrola z trudnością",
        "Bardzo silny przymus, musi dokończyć; potrafi jedynie odwlec",
        "Brak kontroli, przymus całkowicie mimowolny",
    ]),
]

# ---------- Auth ----------
ensure_dirs()
credentials = load_credentials()

# Make sure expected structure exists
credentials.setdefault('credentials', {}).setdefault('usernames', {})
authenticator = stauth.Authenticate(
    credentials['credentials'],
    cookie_name="ocd_app_cookie",
    key="random_signature_key_change_me",
    cookie_expiry_days=7
)

login_response = authenticator.login("Zaloguj się", "main")

if login_response is None:
    name = ""
    username = ""
    authentication_status = None
else:
    name, authentication_status, username = login_response
st.subheader("Zaloguj się")
name, authentication_status, username = authenticator.login(location="main")

if authentication_status is False:
    st.error("Błędny login lub hasło.")
    register_user_ui(credentials, authenticator)
    st.stop()
elif authentication_status is None:
    st.info("Wprowadź dane logowania.")
    if st.session_state.get("just_registered_user"):
        st.success(f"Użytkownik **{st.session_state['just_registered_user']}** został utworzony. Zaloguj się.")
        st.session_state.pop("just_registered_user")
    register_user_ui(credentials, authenticator)
    st.stop()

role = credentials['credentials']['usernames'].get(username, {}).get("role", "user")

# ---------- UI ----------
st.title(APP_TITLE)
authenticator.logout("Wyloguj", "sidebar")
st.sidebar.write(f"Zalogowano: **{name}**  \nRola: **{role}**")

if role == "admin":
    tabs = st.tabs(["Wyniki pacjentów", "Panel admina"])
else:
    tabs = st.tabs(["Lista objawów", "Ocena nasilenia", "Wyniki"])

if role != "admin":
    # --- Tab 1: Lista objawów ---
    with tabs[0]:
        st.header("Lista objawów")
        st.caption("Zaznacz objawy dotyczące pacjenta. Zapis nastąpi po kliknięciu „Zapisz”.")

        user_list = load_user_symptoms(username)
        selected = set(user_list)

        for group, items in SYMPTOMS.items():
            with st.expander(group, expanded=False):
                new_vals = []
                for it in items:
                    key = f"{group}:{it}"
                    checked = st.checkbox(it, value=(key in selected))
                    if checked:
                        new_vals.append(key)
                # Handle "Inne" free text for each group
                inne_key = f"{group}:Inne (dopisz w polu poniżej)"
                if inne_key in new_vals:
                    custom = st.text_input(f"Inne – {group}", value="", placeholder="Opisz własnymi słowami…")
                    if custom.strip():
                        new_vals.append(f"{group}:INNE:{custom.strip()}")

                # merge new selections for this group
                # remove stale keys of this group from selected, then add new
                for k in list(selected):
                    if k.startswith(f"{group}:"):
                        selected.discard(k)
                for k in new_vals:
                    selected.add(k)

        if st.button("Zapisz", type="primary"):
            save_user_symptoms(username, sorted(selected))
            st.success("Zapisano listę objawów.")

    # --- Tab 2: Ocena nasilenia ---
    with tabs[1]:
        st.header("Ocena nasilenia (Y‑BOCS)")
        st.caption("Najpierw wybierz objaw z listy zaznaczonych wcześniej.")

        user_list = load_user_symptoms(username)

        # Show only 'clean' labels to the user
        def nice_label(raw: str) -> str:
            if raw.startswith("Obsesje") or raw.startswith("Kompulsje") or raw.startswith("Rytyny") or raw.startswith("Obsesje religijne") or raw.startswith("Obsesje somatyczne"):
                try:
                    grp, it = raw.split(":", 1)
                    if it.startswith("INNE:"):
                        return f"{grp} – {it[5:]}"
                    return f"{grp} – {it}"
                except ValueError:
                    return raw
            else:
                try:
                    grp, it = raw.split(":", 1)
                    if it.startswith("INNE:"):
                        return f"{grp} – {it[5:]}"
                    return f"{grp} – {it}"
                except ValueError:
                    return raw

        options = {nice_label(o): o for o in user_list}
        sel_label = st.selectbox("Objaw", ["— wybierz —"] + list(options.keys()))
        selected_raw = options.get(sel_label)

        if st.button("Wybierz", disabled=(selected_raw is None)):
            st.session_state["selected_symptom"] = selected_raw

        if st.session_state.get("selected_symptom"):
            st.subheader("Kwestionariusz – ostatni tydzień")
            q_vals = {}
            for idx, (q, choices) in enumerate(YBOCS_ITEMS, start=1):
                val = st.radio(
                    f"{idx}. {q}",
                    options=list(range(5)),
                    format_func=lambda i, ch=choices: f"{i} – {ch[i]}",
                    horizontal=True,
                    key=f"q{idx}"
                )
                q_vals[f"q{idx}"] = int(val)

            suma = sum(q_vals.values())
            st.markdown(f"**Suma punktów: {suma} / 40**")

            if st.button("Zapisz wynik", type="primary"):
                row = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "date": date.today().isoformat(),
                    "user": username,
                    "role": role,
                    "objaw": st.session_state["selected_symptom"],
                    **{k: v for k, v in q_vals.items()},
                    "suma": suma
                }
                append_result(row)
                st.success("Wynik zapisany.")

    results_tab_index = 2
else:
    results_tab_index = 0

# --- Wyniki ---
with tabs[results_tab_index]:
    st.header("Wyniki pacjentów" if role == "admin" else "Wyniki")
    df = load_results()
    if df.empty:
        st.info("Brak wyników.")
    else:
        controls = st.columns(3)

        with controls[0]:
            filter_mode = st.radio("Zakres", ["Zakres dat", "Wybrany dzień"], horizontal=False)
            if filter_mode == "Zakres dat":
                start = st.date_input("Od", value=pd.to_datetime(df["date"].min()).date())
                end = st.date_input("Do", value=pd.to_datetime(df["date"].max()).date())
            else:
                single_day = st.date_input("Dzień", value=pd.to_datetime(df["date"].max()).date())

        with controls[1]:
            if role == "admin":
                available_users = sorted(u for u in df["user"].dropna().unique())
                patient = st.selectbox("Pacjent", ["— wybierz —"] + available_users)
            else:
                patient = username

        with controls[2]:
            if role == "admin":
                if patient in (None, "— wybierz —"):
                    symptom_source = pd.Series(dtype=str)
                else:
                    symptom_source = df.loc[df["user"] == patient, "objaw"]
            else:
                symptom_source = df.loc[df["user"] == username, "objaw"]
            my_symptoms = sorted(set(symptom_source.dropna().tolist()))
            sym_opt = st.selectbox("Objaw", ["(wszystkie)"] + my_symptoms)

        mask = pd.Series(True, index=df.index)
        if filter_mode == "Zakres dat":
            mask &= (pd.to_datetime(df["date"]) >= pd.to_datetime(start)) & (pd.to_datetime(df["date"]) <= pd.to_datetime(end))
        else:
            mask &= pd.to_datetime(df["date"]).dt.date == single_day

        if sym_opt != "(wszystkie)":
            mask &= (df["objaw"] == sym_opt)

        if role == "admin":
            if patient in (None, "— wybierz —"):
                st.info("Wybierz pacjenta, aby zobaczyć wyniki.")
                view = pd.DataFrame(columns=df.columns)
            else:
                mask &= (df["user"] == patient)
                view = df.loc[mask].copy()
        else:
            mask &= (df["user"] == username)
            view = df.loc[mask].copy()

        if not view.empty:
            view["date"] = pd.to_datetime(view["date"])
            view = view.sort_values(["user", "date", "timestamp"])

        st.dataframe(view, use_container_width=True)

        if not view.empty:
            fig, ax = plt.subplots()
            ax.plot(view["date"], view["suma"], marker="o")
            ax.set_xlabel("Data")
            ax.set_ylabel("Suma Y‑BOCS")
            title_user = patient if role == "admin" else username
            ax.set_title(f"Nasilenie w czasie – {title_user}")
            st.pyplot(fig)

if role == "admin":
    with tabs[1]:
        st.header("Panel admina")
        st.caption("Podgląd wyników wszystkich użytkowników oraz eksport.")
        df = load_results()
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Pobierz CSV", data=csv, file_name="wyniki_ocd.csv", mime="text/csv")

        st.subheader("Objawy użytkowników")
        users = [p.name for p in USER_STORE.iterdir() if p.is_dir()]
        for u in sorted(users):
            st.markdown(f"**{u}**")
            try:
                us = load_user_symptoms(u)
                if us:
                    st.write(us)
                else:
                    st.write("— brak —")
            except Exception:
                st.write("— błąd odczytu —")
