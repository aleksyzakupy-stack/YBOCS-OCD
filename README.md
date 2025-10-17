
# Ocena nasilenia OCD – Y‑BOCS (PL)

Aplikacja Streamlit do oceny nasilenia OCD (Y‑BOCS) po polsku, z logowaniem, listą objawów, oceną nasilenia oraz panelem admina.

## Uruchomienie

1. (Opcjonalnie) utwórz i aktywuj wirtualne środowisko.
2. Zainstaluj zależności:
   ```bash
   pip install -r requirements.txt
   ```
3. Upewnij się, że plik `users.yaml` znajduje się w tym samym katalogu co `app.py`.
4. Uruchom aplikację:
   ```bash
   streamlit run app.py
   ```

### Logowanie
Korzysta z `streamlit-authenticator` i pliku `users.yaml`. Domyślny użytkownik ma rolę `admin`.

### Przechowywanie danych
- Dane zapisywane lokalnie w katalogu `data/`:
  - `data/wyniki.csv` – wyniki Y‑BOCS,
  - `data/users/<username>/objawy.json` – zaznaczone objawy użytkownika.

### Funkcje
- Zakładka **Lista objawów** – zaznaczanie objawów (z możliwością dopisania „Inne”), zapis.
- Zakładka **Ocena nasilenia** – wybór objawu z wcześniejszych zaznaczeń, Y‑BOCS (10 pozycji 0–4), zapis wyniku.
- Zakładka **Wyniki** – filtrowanie po dacie i objawie, tabela oraz wykres (matplotlib).
- **Panel admina** – wgląd w dane wszystkich użytkowników + eksport CSV, podgląd zaznaczonych objawów.
