import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import pandas as pd
from datetime import datetime, date
import json
from pathlib import Path
import matplotlib.pyplot as plt
import hashlib

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


def admin_create_user_ui(config: dict, authenticator: stauth.Authenticate):
    st.subheader("Dodaj nowego pacjenta")
    st.caption("Podaj dane logowania pacjenta. Po zapisaniu przekaż pacjentowi login i hasło.")

    with st.form("register_form"):
        first_name = st.text_input("Imię", max_chars=50)
        surname_letters = st.text_input("Pierwsze trzy litery nazwiska", max_chars=3)
        login = st.text_input("Login", max_chars=32)
        submitted = st.form_submit_button("Zapisz konto")

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
    if errors:
        for err in errors:
            st.error(err)
        return

    display_name = f"{first_name_clean.title()} {letters_clean.upper()}"
    hashed_password = stauth.Hasher.hash(password)

    config['credentials']['usernames'][login_clean] = {
        "email": f"{login_clean}@example.com",
        "name": display_name,
        "password": hashed_password,
        "role": "user",
        "force_password_reset": True,
    }

    save_credentials(config)
    if hasattr(authenticator, "credentials"):
        authenticator.credentials = config['credentials']

    st.success(f"Dodano pacjenta **{display_name}** (login: {login_clean}).")
    st.rerun()

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


def widget_key_for(username: str, raw_key: str) -> str:
    """Generate a stable, unique widget key for Streamlit elements."""
    digest = hashlib.sha1(f"{username}:{raw_key}".encode("utf-8")).hexdigest()
    return f"widget_{digest}"


def render_symptom_editor(target_username: str):
    st.caption('Zaznacz objawy dotyczące pacjenta. Zapis nastąpi po kliknięciu „Zapisz objawy”.')

    user_list = load_user_symptoms(target_username)
    selected = set(user_list)

    widget_user = target_username or "anon"
    for group, items in SYMPTOMS.items():
        with st.expander(group, expanded=False):
            new_vals = []
            group_prefix = f"{group}:"
            inne_key = f"{group}:Inne (dopisz w polu poniżej)"
            custom_entries = [k for k in selected if k.startswith(f"{group}:INNE:")]
            stored_custom_text = custom_entries[0].split(":", 2)[2] if custom_entries else ""
            inne_selected_stored = inne_key in selected
            inne_default_checked = inne_selected_stored or bool(custom_entries)

            for it in items:
                base_key = f"{group}:{it}"
                widget_key = widget_key_for(widget_user, base_key)
                if it.startswith("Inne"):
                    checked = st.checkbox(it, value=inne_default_checked, key=widget_key)
                    text_key = f"{widget_key}_text"
                    if checked:
                        custom_input = st.text_input(
                            f"Inne – {group}",
                            value=stored_custom_text,
                            placeholder="Opisz własnymi słowami…",
                            key=text_key,
                        )
                        custom_input_clean = custom_input.strip()
                        if custom_input_clean:
                            new_vals.append(f"{group}:INNE:{custom_input_clean}")
                        else:
                            new_vals.append(inne_key)
                    else:
                        if text_key in st.session_state:
                            st.session_state.pop(text_key)
                else:
                    checked = st.checkbox(it, value=(base_key in selected), key=widget_key)
                    if checked:
                        new_vals.append(base_key)

            for k in list(selected):
                if k.startswith(group_prefix):
                    selected.discard(k)
            for k in new_vals:
                selected.add(k)

    if st.button("Zapisz objawy", type="primary", key=f"save_symptoms_{target_username}"):
        save_user_symptoms(target_username, sorted(selected))
        st.success("Zapisano listę objawów.")

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

authenticator.login(
    location="main",
    fields={
        "Form name": "Zaloguj się",
        "Username": "Login",
        "Password": "Hasło",
        "Login": "Zaloguj się"
    }
)

name = st.session_state.get("name", "")
username = st.session_state.get("username", "")
authentication_status = st.session_state.get("authentication_status")

st.subheader("Zaloguj się")

if authentication_status is False:
    st.error("Błędny login lub hasło.")
    st.info("Jeśli nie masz konta, skontaktuj się z administratorem aplikacji.")
    st.stop()
elif authentication_status is None:
    st.info("Wprowadź dane logowania.")
    st.info("Jeśli nie masz konta, skontaktuj się z administratorem aplikacji.")
    st.stop()

role = credentials['credentials']['usernames'].get(username, {}).get("role", "user")
user_record = credentials['credentials']['usernames'].get(username, {})

if user_record.get("force_password_reset"):
    st.warning(
        "To Twoje pierwsze logowanie. Ustaw nowe hasło, aby kontynuować korzystanie z aplikacji."
    )

    with st.form(f"force_password_reset_{username}"):
        new_password = st.text_input("Nowe hasło", type="password")
        new_password_repeat = st.text_input("Powtórz nowe hasło", type="password")
        submitted = st.form_submit_button("Ustaw hasło")

    if submitted:
        errors = []
        if not new_password:
            errors.append("Hasło nie może być puste.")
        if new_password != new_password_repeat:
            errors.append("Hasła muszą być identyczne.")

        if errors:
            for err in errors:
                st.error(err)
        else:
            user_record["password"] = stauth.Hasher.hash(new_password)
            user_record["force_password_reset"] = False
            save_credentials(credentials)
            if hasattr(authenticator, "credentials"):
                authenticator.credentials = credentials['credentials']
            st.session_state["password_reset_done"] = "Hasło zostało ustawione. Możesz kontynuować pracę w aplikacji."
            st.rerun()

    st.stop()

# ---------- UI ----------
st.title(APP_TITLE)
authenticator.logout("Wyloguj", "sidebar")
st.sidebar.write(f"Zalogowano: **{name}**  \nRola: **{role}**")

if role == "admin":
    tabs = st.tabs(["Pacjenci", "Objawy pacjentów", "Wyniki pacjentów"])
    patients_tab, symptoms_tab, results_tab = tabs

    with patients_tab:
        st.header("Zarządzanie pacjentami")
        admin_create_user_ui(credentials, authenticator)

        st.subheader("Istniejące konta")
        users_rows = []
        for login, data in sorted(credentials['credentials']['usernames'].items()):
            users_rows.append({
                "Login": login,
                "Nazwa": data.get("name", ""),
                "Rola": data.get("role", "user")
            })
        if users_rows:
            users_df = pd.DataFrame(users_rows)
            st.dataframe(users_df, width="stretch")
        else:
            st.info("Brak zarejestrowanych kont.")

    with symptoms_tab:
        st.header("Objawy pacjentów")
        patient_options = [
            (login, data.get("name", login))
            for login, data in sorted(credentials['credentials']['usernames'].items())
            if data.get("role", "user") == "user"
        ]
        if not patient_options:
            st.info('Brak pacjentów do konfiguracji. Dodaj konto w zakładce „Pacjenci”.')
        else:
            patient_lookup = dict(patient_options)
            display_to_login = {f"{name} ({login})": login for login, name in patient_options}
            labels = list(display_to_login.keys())
            selected_label = st.selectbox("Pacjent", ["— wybierz —"] + labels)
            selected_patient = display_to_login.get(selected_label)

            if selected_patient:
                patient_name = patient_lookup[selected_patient]
                st.markdown(f"**Wybrany pacjent:** {patient_name} ({selected_patient})")
                render_symptom_editor(selected_patient)

    with results_tab:
        st.header("Wyniki pacjentów")
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
                patient_options = [
                    (login, data.get("name", login))
                    for login, data in sorted(credentials['credentials']['usernames'].items())
                    if data.get("role", "user") == "user"
                ]
                patient_display = {f"{name} ({login})": login for login, name in patient_options}
                patient_labels = ["— wybierz —"] + list(patient_display.keys())
                selected_label = st.selectbox("Pacjent", patient_labels)
                patient = patient_display.get(selected_label)

            with controls[2]:
                if patient in (None, "— wybierz —"):
                    symptom_source = pd.Series(dtype=str)
                else:
                    symptom_source = df.loc[df["user"] == patient, "objaw"]
                my_symptoms = sorted(set(symptom_source.dropna().tolist()))
                sym_opt = st.selectbox("Objaw", ["(wszystkie)"] + my_symptoms)

            mask = pd.Series(True, index=df.index)
            if filter_mode == "Zakres dat":
                mask &= (pd.to_datetime(df["date"]) >= pd.to_datetime(start)) & (pd.to_datetime(df["date"]) <= pd.to_datetime(end))
            else:
                mask &= pd.to_datetime(df["date"]).dt.date == single_day

            if sym_opt != "(wszystkie)":
                mask &= (df["objaw"] == sym_opt)

            if patient in (None, "— wybierz —"):
                st.info("Wybierz pacjenta, aby zobaczyć wyniki.")
                view = pd.DataFrame(columns=df.columns)
            else:
                mask &= (df["user"] == patient)
                view = df.loc[mask].copy()

            if not view.empty:
                view["date"] = pd.to_datetime(view["date"])
                view = view.sort_values(["user", "date", "timestamp"])

            st.dataframe(view, width="stretch")

            if not view.empty:
                fig, ax = plt.subplots()
                ax.plot(view["date"], view["suma"], marker="o")
                ax.set_xlabel("Data")
                ax.set_ylabel("Suma Y‑BOCS")
                ax.set_title(f"Nasilenie w czasie – {patient}")
                st.pyplot(fig)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Pobierz CSV", data=csv, file_name="wyniki_ocd.csv", mime="text/csv")
else:
    tabs = st.tabs(["Ocena nasilenia", "Wyniki"])
    severity_tab, results_tab = tabs

    with severity_tab:
        st.header("Ocena nasilenia (Y‑BOCS)")
        st.caption("Wybierz objaw przypisany przez terapeutę i oceń nasilenie z ostatniego tygodnia.")
        user_list = load_user_symptoms(username)

        if not user_list:
            st.info("Brak przypisanych objawów. Skontaktuj się z terapeutą lub administratorem.")
        else:
            def nice_label(raw: str) -> str:
                try:
                    grp, it = raw.split(":", 1)
                    if it.startswith("INNE:"):
                        return f"{grp} – {it[5:]}"
                    return f"{grp} – {it}"
                except ValueError:
                    return raw

            options = {nice_label(o): o for o in user_list}
            sel_label = st.selectbox("Objaw", ["— wybierz —"] + list(options.keys()))
            if sel_label != "— wybierz —":
                selected_raw = options[sel_label]
                st.subheader("Kwestionariusz – ostatni tydzień")
                q_vals = {}
                for idx, (q, choices) in enumerate(YBOCS_ITEMS, start=1):
                    radio_key = widget_key_for(username, f"severity:{selected_raw}:q{idx}")
                    val = st.radio(
                        f"{idx}. {q}",
                        options=list(range(5)),
                        format_func=lambda i, ch=choices: f"{i} – {ch[i]}",
                        horizontal=True,
                        key=radio_key
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
                        "objaw": selected_raw,
                        **{k: v for k, v in q_vals.items()},
                        "suma": suma
                    }
                    append_result(row)
                    st.success("Wynik zapisany.")

    with results_tab:
        st.header("Wyniki")
        df = load_results()
        if df.empty:
            st.info("Brak wyników.")
        else:
            controls = st.columns(2)

            with controls[0]:
                filter_mode = st.radio("Zakres", ["Zakres dat", "Wybrany dzień"], horizontal=False)
                if filter_mode == "Zakres dat":
                    start = st.date_input("Od", value=pd.to_datetime(df["date"].min()).date())
                    end = st.date_input("Do", value=pd.to_datetime(df["date"].max()).date())
                else:
                    single_day = st.date_input("Dzień", value=pd.to_datetime(df["date"].max()).date())

            with controls[1]:
                symptom_source = df.loc[df["user"] == username, "objaw"]
                my_symptoms = sorted(set(symptom_source.dropna().tolist()))
                sym_opt = st.selectbox("Objaw", ["(wszystkie)"] + my_symptoms)

            mask = pd.Series(True, index=df.index)
            if filter_mode == "Zakres dat":
                mask &= (pd.to_datetime(df["date"]) >= pd.to_datetime(start)) & (pd.to_datetime(df["date"]) <= pd.to_datetime(end))
            else:
                mask &= pd.to_datetime(df["date"]).dt.date == single_day

            mask &= (df["user"] == username)

            if sym_opt != "(wszystkie)":
                mask &= (df["objaw"] == sym_opt)

            view = df.loc[mask].copy()

            if not view.empty:
                view["date"] = pd.to_datetime(view["date"])
                view = view.sort_values(["date", "timestamp"])

            st.dataframe(view, width="stretch")

            if not view.empty:
                fig, ax = plt.subplots()
                ax.plot(view["date"], view["suma"], marker="o")
                ax.set_xlabel("Data")
                ax.set_ylabel("Suma Y‑BOCS")
                ax.set_title("Nasilenie w czasie")
                st.pyplot(fig)
