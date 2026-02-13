import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import pandas as pd
import threading
import os
import sys
import socket
import numpy as np

from python_vesla import vedenkorkeus_API, pivot_ja_tallennus, prosentti_pisteet, pysyvyydet, linechart, viimeisin_havainto_päivitys

## Luokka jossa määritellän käyttöliittymä ja kaikki siihen liittyvät toiminnot
class VedenkorkeusTab:
    def __init__(self, parent, stations_df):
        self.parent = parent
        self.frame = ttk.Frame(parent)
        self.stations_df = stations_df 
        # --- Luokan muuttujien määrittäminen ---
        self.station_var = tk.StringVar()
        self.tasokorkeus_var = tk.StringVar()
        self.maakunta_var = tk.StringVar(value="All")
        self.active_var = tk.BooleanVar()
        self.tallennus_var = tk.BooleanVar()
        self.pivot_var = tk.BooleanVar()
        self.prosentti_var = tk.BooleanVar()
        self.pysyvyydet_var = tk.BooleanVar()
        self.custom_range_var = tk.BooleanVar()
        self.custom_name_var  = tk.StringVar(value="Valittu_jakso")
        self.custom_start_var = tk.StringVar(value="04-01")
        self.custom_end_var   = tk.StringVar(value="06-15")
        self.save_path = None
        self.save_path1 = None
        self.save_path_var = tk.StringVar(value="Pivotoidun datan tallennuspolku: ei valittu")
        self.save_path1_var = tk.StringVar(value="Muuttumattoman datan tallennuspolku: ei valittu")
        self.status_text_var = tk.StringVar(value="Idle")

        # --- Vedenkorkeusasemien lataaminen ---
        self.stations_df["display"] = self.stations_df["Nimi"] + " - " + self.stations_df["Tunnus"]

        # Alasvetovalikon hakemisto ja muut lookupit
        self.station_lookup = {row.display: row for row in self.stations_df.itertuples()}
        self.display_to_id = dict(zip(self.stations_df["display"], self.stations_df["Tunnus"]))
        self.search_index = {f"{row.Tunnus} {row.Nimi}".lower(): row.Tunnus for row in self.stations_df.itertuples()}
        maakunnat = sorted(self.stations_df["Maakunta"].dropna().unique().tolist())
        maakunnat.insert(0, "All")
        self.maakunnat = maakunnat

        # --- rakennetaan GUI ---
        self.build_gui()

    # ---------------- GUIn rakentaminen ----------------
    def build_gui(self):
        # --- INTERNAL NOTEBOOK (inside this tab) ---
        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill="both", expand=True)

        # ===============================
        # PÄÄSIVU
        # ===============================
        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text="Pääsivu")

        # ===============================
        # OHJEET
        # ===============================
        metadata_frame = ttk.Frame(notebook)
        notebook.add(metadata_frame, text="Ohjeet")

        # ===============================
        # TUNNUSLUKUJEN SELITYKSET
        # ===============================
        explanations_frame = ttk.Frame(notebook)
        notebook.add(explanations_frame, text="Tunnuslukujen selitykset")
        self.create_explanations_tab(explanations_frame)

        # ===============================
        # PÄIVITYS
        # ===============================
        update_frame = ttk.Frame(notebook)
        notebook.add(update_frame, text="Päivitys")
        self.build_update_tab(update_frame)

        # ===============================
        # VIERITETTÄVÄ PÄÄSIVU
        # ===============================
        container = ttk.Frame(main_frame)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)

        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ===============================
        # MAAKUNTA + AKTIIVISET ASEMAT
        # ===============================
        tk.Label(scrollable_frame, text="Maakunta").pack(anchor="w", padx=10, pady=(8, 0))

        maakunta_row = tk.Frame(scrollable_frame)
        maakunta_row.pack(anchor="w", padx=10, pady=(0, 5), fill="x")

        maakunta_combo = ttk.Combobox(
            maakunta_row,
            textvariable=self.maakunta_var,
            values=self.maakunnat,
            state="readonly",
            width=30
        )
        maakunta_combo.pack(side="left")
        maakunta_combo.bind("<<ComboboxSelected>>", lambda e: self.filter_stations())

        tk.Checkbutton(
            maakunta_row,
            text="Vain jatkuvat asemat",
            variable=self.active_var,
            command=self.filter_stations
        ).pack(side="left", padx=(15, 0))

        # ===============================
        # ASEMA + TASOKORKEUS
        # ===============================
        station_label_row = tk.Frame(scrollable_frame)
        station_label_row.pack(anchor="w", padx=8, pady=(0, 5), fill="x")

        station_row = tk.Frame(scrollable_frame)
        station_row.pack(anchor="w", padx=8, pady=(0, 5), fill="x")

        tk.Label(
            station_label_row,
            text="Valitse havaintoasema"
        ).pack(side="left", padx=(5, 45), pady=(5, 0))

        tk.Label(
            station_label_row,
            text="Valitse tasokorkeus"
        ).pack(side="left", padx=(45, 0), pady=(5, 0))

        self.station_combo = ttk.Combobox(
            station_row,
            textvariable=self.station_var,
            values=sorted(self.stations_df["display"].tolist()),
            width=30
        )
        self.station_combo.pack(side="left", padx=(0, 5))
        self.station_combo.bind("<KeyRelease>", lambda e: self.filter_stations())
        self.station_combo.bind("<<ComboboxSelected>>", self.on_station_selected)

        self.tasokorkeus_combo = ttk.Combobox(
            station_row,
            textvariable=self.tasokorkeus_var,
            values=[],
            state="readonly",
            width=17
        )
        self.tasokorkeus_combo.pack(side="left", padx=(5, 0))

        # ===============================
        # ENSIMMÄINEN / VIIMEINEN HAVAinto
        # ===============================
        self.first_obs_var = tk.StringVar(value="Ensimmäinen havainto: –")
        self.last_obs_var = tk.StringVar(value="Viimeisin havainto: –")

        tk.Label(scrollable_frame, textvariable=self.first_obs_var).pack(anchor="w", padx=10)
        tk.Label(scrollable_frame, textvariable=self.last_obs_var).pack(anchor="w", padx=10)

        # ===============================
        # AIKAVÄLI
        # ===============================
        date_row = tk.Frame(scrollable_frame)
        date_row.pack(anchor="w", padx=10, pady=(8, 0), fill="x")

        start_frame = tk.Frame(date_row)
        start_frame.pack(side="left")

        tk.Label(start_frame, text="Alku pvm. (YYYY-MM-DD)").pack(anchor="w")
        self.start_entry = tk.Entry(start_frame, width=12)
        self.start_entry.insert(0, "2024-01-01")
        self.start_entry.pack(anchor="w")

        end_frame = tk.Frame(date_row)
        end_frame.pack(side="left", padx=(20, 0))

        tk.Label(end_frame, text="Loppu pvm. (YYYY-MM-DD)").pack(anchor="w")
        self.end_entry = tk.Entry(end_frame, width=12)
        self.end_entry.insert(0, datetime.today().strftime("%Y-%m-%d"))
        self.end_entry.pack(anchor="w")

        # ===============================
        # KÄYTTÄJÄN MÄÄRITTELEMÄ JAKSO
        # ===============================
        tk.Checkbutton(
            scrollable_frame,
            text="Laske min ja max käyttäjän määrittelemälle jaksolle",
            variable=self.custom_range_var
        ).pack(anchor="w", padx=10, pady=(15, 0))

        custom_frame = tk.Frame(scrollable_frame)
        custom_frame.pack(anchor="w", padx=20, pady=(5, 0))

        tk.Label(custom_frame, text="Alku (MM-DD)").grid(row=1, column=0, sticky="w", padx=(0, 5))
        tk.Entry(custom_frame, textvariable=self.custom_start_var, width=8).grid(row=1, column=1, sticky="w", padx=(0, 15))

        tk.Label(custom_frame, text="Loppu (MM-DD)").grid(row=1, column=2, sticky="w", padx=(0, 5))
        tk.Entry(custom_frame, textvariable=self.custom_end_var, width=8).grid(row=1, column=3, sticky="w")

        # ===============================
        # TALLENNUS + AJO
        # ===============================
        self.create_save_options(scrollable_frame)

        tk.Button(
            scrollable_frame,
            text="Run",
            command=self.run_analysis,
            width=20
        ).pack(anchor="w", padx=10, pady=(15, 5))

        tk.Label(
            scrollable_frame,
            textvariable=self.status_text_var,
            fg="blue"
        ).pack(pady=(5, 10))

        # ===============================
        # METADATA
        # ===============================
        self.create_metadata_tab(metadata_frame)


    def create_explanations_tab(self, parent):
        """Creates the tab that explains the statistical metrics"""
        container = tk.Frame(parent)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        
        scrollbar = tk.Scrollbar(container)
        scrollbar.pack(side="right", fill="y")
        
        text_widget = tk.Text(container, wrap="word", yscrollcommand=scrollbar.set, width=80, height=25)
        text_widget.pack(side="left", fill="both", expand=True)
        
        explanation_text = """
Selaimeen avautuvan ikkunan tunnuslukujen selitykset:

- HW (Highest Water): Korkein havaittu vedenkorkeus.
- MHW (Mean High Water): Keskimääräinen ylin vedenkorkeus.
- MW (Mean Water): Keskimääräinen vedenkorkeus koko havaintojaksolla.
- MNW (Mean Low Water): Keskimääräinen alin vedenkorkeus.
- NW (Lowest Water): Alin havaittu vedenkorkeus.
- HW-NW: Korkeimman ja alimman vedenkorkeuden erotus.
- KVV: Keskimääräinen vuosivaihtelu (vuosittaisen vaihteluvälin keskiarvo).
- Q99: Vedenkorkeus jonka alapuolella 99 prosenttia havainnoista on
- Q95: Vedenkorkeus jonka alapuolella 95 prosenttia havainnoista on
- Q05: Vedenkorkeus jonka alapuolella  5 prosenttia havainnoista on
- n: havaintojen lukumäärä.

vuodenajat
talvi: joulu-helmi
kevät: maalis-touko
kesä: kesä-elo
sysky: syys-marras

Tunnusluvut on esitetty sekä koko haetulle jaksolle että valitulle vuodelle
    """
        text_widget.insert("end", explanation_text)
        text_widget.configure(state="disabled")
        scrollbar.config(command=text_widget.yview)

    def build_update_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(
            frame,
            text="Päivitä asemien viimeisin havainto",
            font=("Segoe UI", 11, "bold")
        ).pack(pady=(0, 20))

        self.update_status_var = tk.StringVar(value="Ei käynnissä")

        ttk.Button(
            frame,
            text="Päivitä viimeisin havainto",
            width=30,
            command=self.paivita_viimeisin_havainto
        ).pack(pady=(0, 15))

        ttk.Label(
            frame,
            textvariable=self.update_status_var,
            foreground="blue"
        ).pack()

    def refresh_station_data(self):
        """Refresh station-related UI and lookups after stations_df changes"""

        # Recreate display column
        self.stations_df["display"] = (
            self.stations_df["Nimi"] + " - " + self.stations_df["Tunnus"]
        )

        # Rebuild lookups
        self.station_lookup = {
            row.display: row for row in self.stations_df.itertuples()
        }
        self.display_to_id = dict(
            zip(self.stations_df["display"], self.stations_df["Tunnus"])
        )
        self.search_index = {
            f"{row.Tunnus} {row.Nimi}".lower(): row.Tunnus
            for row in self.stations_df.itertuples()
        }

        # Refresh combobox values
        new_values = sorted(self.stations_df["display"].tolist())
        self.station_combo["values"] = new_values

        # If a station is selected, refresh labels
        selected = self.station_var.get()
        if selected in self.station_lookup:
            station = self.station_lookup[selected]
            self.first_obs_var.set(
                f"Ensimmäinen havainto: {station.EnsimmainenHavainto}"
            )
            self.last_obs_var.set(
                f"Viimeisin havainto: {station.ViimeisinHavainto}"
            )
        else:
            self.first_obs_var.set("Ensimmäinen havainto: –")
            self.last_obs_var.set("Viimeisin havainto: –")


    def paivita_viimeisin_havainto(self):
        try:
            self.update_status_var.set("Päivitys käynnissä...")
            self.frame.update_idletasks()

            self.stations_df = viimeisin_havainto_päivitys(self.stations_df)
            stations_df_to_be_saved = self.stations_df.drop(columns=["display"])
            excel_path = self.get_resource_path("Vedenkorkeusasemat_kaikki_tasotiedot.csv")
            stations_df_to_be_saved.to_csv(excel_path,sep=";",encoding="cp1252",index=False)
            self.refresh_station_data()
            self.update_status_var.set("Päivitys valmis")
            messagebox.showinfo("Valmis", "Viimeisin havainto päivitetty onnistuneesti.")

        except Exception as e:
            self.update_status_var.set("Virhe päivityksessä")
            messagebox.showerror("Virhe", str(e))

        except Exception as e:
            messagebox.showerror("Virhe", str(e))
            self.status_text_var.set("Idle")

    # ---------------- Helper GUI methods ----------------
    def create_save_options(self, parent):
        valinta_teksti = tk.StringVar(value="Tallennus valinnat")
        tk.Label(parent, textvariable=valinta_teksti).pack(anchor="w", pady=(20,0))

        # Original data
        row_frame = tk.Frame(parent)
        row_frame.pack(anchor="w", padx=10, pady=(10,0), fill="x")
        tk.Checkbutton(row_frame, text="Tallennetaanko alkuperäinen data?", variable=self.tallennus_var).pack(side="left")
        tk.Button(row_frame, text="Valitse tallennuspolku", command=self.select_original_path, width=22, pady=1).pack(side="left", padx=(10,0))
        tk.Label(parent, textvariable=self.save_path1_var, wraplength=450, fg="gray").pack(anchor="w")

        # Pivot data
        pivot_row_frame = tk.Frame(parent)
        pivot_row_frame.pack(anchor="w", padx=10, pady=(10,0), fill="x")
        tk.Checkbutton(pivot_row_frame, text="Pivotoitointi ja tallennus", variable=self.pivot_var).pack(side="left")
        tk.Button(pivot_row_frame, text="Valitse tallenuspolku", command=self.select_pivot_path, width=22, pady=1).pack(side="left", padx=(10,0))
        tk.Label(parent, textvariable=self.save_path_var, wraplength=450, fg="gray").pack(anchor="w")

        # Options
        tk.Checkbutton(parent, text="Prosenttipisteiden laskeminen (vaatii pivotoinnin)", variable=self.prosentti_var).pack(anchor="w", padx=10, pady=(10,0))
        tk.Checkbutton(parent, text="Pysyvyyksien laskeminen (vaatii pivotoinnin)", variable=self.pysyvyydet_var).pack(anchor="w", padx=10, pady=(10,0))

    def create_metadata_tab(self, parent):
        text_container = tk.Frame(parent)
        text_container.pack(fill="both", expand=True, padx=10, pady=10)
        scrollbar = tk.Scrollbar(text_container)
        scrollbar.pack(side="right", fill="y")
        metadata_text = tk.Text(text_container, wrap="word", yscrollcommand=scrollbar.set, width=80, height=25)
        metadata_text.pack(side="left", fill="both", expand=True)
        metadata_text.insert("end", """\
    
Tervetuloa käyttämään vedenkorkeustyökalua työkalua vedenkorkeushavaintojen hakemiseen, tallentamiseen visualisointiin ja analysointiin!

Yleistä työkalusta:
                     
Työkalu on tehty helpottamaan vedenkorkeushavaintotietojen hakemisen hydrologia rajapinnan kautta.
Työkalulla on kaksi eri toiminnallisuutta havaintojen hakemisen lisäksi:
                     
1. Tulosten pivotointi sekä tunnuslukujen (min, max, avg, mediaani), pysyvyyksien ja prosenttipisteiden laskeminen.
sekä näiden tietojen tallentaminen Excel-tiedostoon. Työkalu laskee myös haetun aikasarjan HW, MHW, MW, MNW, NW, Q95 ja Q05 arvot ja tallentaa ne erilliseen välilehteen.

2. Tulosten visualisointi siten että graafissa esitetään havaintojakson minimi, maksimi ja keskiarvo sekä
valitun vuoden vedenkorkeushavainnot. Lisäksi kuvaajaan voidaan lisätä säännöstelyrajat erillisestä Excel-tiedostosta.
                     
Lyhyet käyttöohjeet
                     
Datan hakeminen:
                     
1. Valitsemalla "Maakunta"-valikosta maakunta voidaan suodattaa asema-valikko näyttämään ainoastaan valitun maakunnan havainto-asemat.
2. Klikkaamalla "Vain jatkuvat asemat" täppä voidaan suodattaa asema-valikko näyttämään ainoastaan havainto-asemat, joiden tila on jatkuva
3. Havaintoasema valitaan vedettävästä valikosta. Tekstikenttään voidaan myös kirjoittaa aseman tunnuksen tai nimen alkuosa, jolloin valikko suodattaa vain niitä vastaavat asemat.
4. Korkeusaseman tasokorjaus valitaan erillisestä vedettävästä valikosta. Mikäli valikossa lukee "Ei saatavilla" niin kyseiselle asemalle ei ole tallennettu tasokorjaustietoa.
5. Kun asema on valittu, näytetään alapuolella kyseisen aseman ensimmäinen ja viimeinen havainto.
6. Seuraavaksi valitaan alku- ja loppupäivämäärä. Vedenkorkeushavainnot haetaan ja tunnusluvut lasketaan tältä aikaväliltä
7. Mikäli minimi ja maksimi halutaan laskea myös ennalta määrättyjen vuodenikohtaisten jaksojen (esim. talvi, kevät, kesä, syksy) lisäksi käyttäjän määrittelemälle jaksolle, voidaan se määritellä syöttämällä haluttu alku- ja loppupvm. muodossa MM-DD ja klikkaamalla "Laske min ja max käyttäjän määrittelemälle jaksolle" täppä.

Tallentaminen:

1. Jos halutaan tallentaa alkuperäisen datan (1 havainto per rivi) klikataan ensimmäinen täppä ja annetaan tiedostosijainti klikkaamalla nappia.
2. Jos halutaan tehdä datan pivointi ja tallentaa pivotoitu data (sisältää min, max, ka ja med) klikataan sitä vastaava täppä ja annetaan tiedosto sijainti.
3. Jos pivotoituun tiedostoon halutaan lisäksi laskea prosenttipisteet (5, 10, 25, 50, 75, 90 ja 95) klikataan täppä.
4. Jos halutaan laskea pysyvyydet niin klikataan täppä. Pysyvyyksien ja prosenttipisteiden laskenta vaatii että pivotointi on myös tehty.
5. Molemmissa tapauksissa tallennus tapahtuu Excel-tiedostoon, joihin lasketaan myös alkuperäinen datan yli, ali ja keskivedet.

Visualisointi:

1. Kun data on haettu onnistuneesti aukeaa ponnahdusikkuna, jossa kysytään halutaanko dataa katsella interaktiivisessa kuvaajassa.
2. Mikäli valitaa kyllä niin seuraavaksi kysytään halutaanko kuvaajaan lisätä säännöstelyrajat. Säännöstelyrajat lisätään erillillä Excel-tiedostolla
3. Kun valinnat on tehty, aukeaa kuvaaja selaimeen. Kuvaajan yläosassa voidaan valita se vuosi, joka halutaa visualisoida.
4. Samaan aikaan voidaan visualisoida joko 1 tai 2 vuotta. 2 vuoden visualisointi vaatii checkboxin aktiiviseksi klikkaamisen. 
5. Kuvaajan selitteestä voidaan klikata pois näkyvistä ja takaisin näkyville data-sarjoja.
6. Viemällä hiiri kuvaajan päälle, ilmestyy tekstiboksi jossa on sen aikahetken arvot. Klikkaamalla kuvaajaa voidaan tallentaa näkyville sen aikahetken arvo.
7. Clear lines toiminnolla saadaan tyhjennettyä tallennetut arvot kuvaajasta.
8. Kuvaajan oikealla puolella on esitetty olennaisimmat tunnusluvut sekä koko ajanjaksolle että valituille vuosille. Tiedot voi kopioida maalaamalla esim. Exceliin.
                     
""")
        scrollbar.config(command=metadata_text.yview)
        metadata_text.configure(state="disabled")

    # ---------------- File Dialogs ----------------
    def select_original_path(self):
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files","*.xlsx")], title="Save original data as")
        if path:
            self.save_path1 = path
            self.save_path1_var.set(path)

    def select_pivot_path(self):
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files","*.xlsx")], title="Save pivoted data as")
        if path:
            self.save_path = path
            self.save_path_var.set(path)

    # ---------------- Station Filtering ----------------
    def filter_stations(self):
        typed = self.station_var.get().lower() if self.station_var.get() else ""
        df_filtered = self.stations_df.copy()
        if self.active_var.get():
            df_filtered = df_filtered[df_filtered["Tila"]=="Jatkuva"]
        if self.maakunta_var.get() != "All":
            df_filtered = df_filtered[df_filtered["Maakunta"] == self.maakunta_var.get()]
        if typed:
            df_filtered = df_filtered[df_filtered["display"].str.lower().str.contains(typed)]
        new_values = sorted(df_filtered["display"].tolist())
        self.station_combo["values"] = new_values
        if typed and self.station_var.get() not in new_values:
            self.first_obs_var.set("Ensimmäinen havainto: –")
            self.last_obs_var.set("Viimeisin havainto: –")
        self.station_combo.update()

    # ---------------- Station Selected ----------------
    def on_station_selected(self, event=None):
        selected = self.station_var.get()
        if selected not in self.station_lookup:
            self.first_obs_var.set("Ensimmäinen havainto: –")
            self.last_obs_var.set("Viimeisin havainto: –")
            self.tasokorkeus_combo["values"] = []
            self.tasokorkeus_var.set("")
            return
        station = self.station_lookup[selected]
        self.first_obs_var.set(f"Ensimmäinen havainto: {station.EnsimmainenHavainto}")
        self.last_obs_var.set(f"Viimeisin havainto: {station.ViimeisinHavainto}")
        available_levels = []
        for level in ["N2000","N60","NN43","LN","NN"]:
            value = getattr(station, level, None)
            if pd.notna(value):
                available_levels.append(f"{level} ({value})")
        self.tasokorkeus_combo["values"] = available_levels
        if available_levels:
            self.tasokorkeus_combo.set(available_levels[0])
            self.tasokorkeus_combo.config(state="readonly")
        else:
            self.tasokorkeus_combo.set("")
            self.tasokorkeus_combo.config(state="disabled")

    def get_resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    # ---------------- RUN ANALYSIS ----------------

    ## Varsinainen laskenta ja datan hakeminen tapahtuu tässä funktiossa. Funktio on pitkä, mutta se on jaettu loogisiin osiin kommenttien avulla, jotta sen seuraaminen on helpompaa.
    def run_analysis(self):

        ## Käyttäjän syötteiden validointi ja datan hakeminen API:sta
        try:
            start_date = self.start_entry.get()
            end_date = self.end_entry.get()
            selected = self.station_var.get()

            # --- Determine station ID ---
            if selected in self.display_to_id:
                station_id = self.display_to_id[selected]
            else:
                match = None
                for key, sid in self.search_index.items():
                    if selected.lower() in key:
                        match = sid
                        break
                if match:
                    station_id = match
                else:
                    messagebox.showerror("Virhe","Asemaa ja ID:tä ei voitu yhdistää. Tarkista aseman valinta.")
                    return

            # --- Validate dates ---
            datetime.strptime(start_date,"%Y-%m-%d")
            datetime.strptime(end_date,"%Y-%m-%d")

            self.status_text_var.set(f"Haetaan arvoja asemalle: {station_id}...")
            self.frame.update()

            # --- Tasokorkeus ---
            tasokorjaus = self.tasokorkeus_var.get()
            if tasokorjaus in [None,"","Ei saatavilla"]:
                level, value = None, None
            else:
                level = tasokorjaus.split("(")[0].strip()
                value_str = tasokorjaus.split("(")[1].replace(")","").strip()
                try: value = float(value_str)
                except: value=None

            # --- Varsinainen datan hakeminen hydrologisen rajapinnan kautta tapahtuu tässä vedenkorkeus_API function avulla, joka sijaitsee tiedostossa python_vesla ---
            df = vedenkorkeus_API(start_date,end_date,station_id,level,value)
            if df is None or df.empty:
                messagebox.showerror("Virhe","API:sta ei saatu dataa")
                self.status_text_var.set("Idle")
                return

            self.status_text_var.set(f"Arvot haettu: {len(df)} rows")

            # --- Tunnuslukujen laskeminen koko haetulle aikajaksolle ---
            variable_name = level if level else "Arvo"
            df[variable_name] = pd.to_numeric(df[variable_name], errors="coerce")
            yearly_max = df.groupby("Vuosi")[variable_name].max()
            yearly_min = df.groupby("Vuosi")[variable_name].min()
            yearly_range = yearly_max - yearly_min
            ## Keskimääräinen vuosivaihtelu koko jaksolle
            KVV = yearly_range.mean()
            HW  = df[variable_name].max()
            NW  = df[variable_name].min()
            MW  = df[variable_name].mean()
            vaihteluväli = HW - NW
            KVV = yearly_range.mean()
            Q99 = df[variable_name].quantile(0.99)
            Q95 = df[variable_name].quantile(0.95)
            Q05 = df[variable_name].quantile(0.05)
            MHW = yearly_max.mean()
            MNW = yearly_min.mean()
            total_valid_obs = int(df[variable_name].count())
            stats_df = pd.DataFrame([{"HW":HW,"MHW":MHW,"MW":MW,"MNW":MNW,"NW":NW, "HW-NW": vaihteluväli,"KVV":KVV,"Q99":Q99, "Q95":Q95,"Q05":Q05, "n": total_valid_obs}])
            level_cols = ["HW", "MHW", "MW", "MNW", "NW", "HW-NW", "KVV", "Q99", "Q95", "Q05"]
            stats_df[level_cols] = stats_df[level_cols] * 0.01  # Convert level columns to meters

            ## Tunnuslukuken laskeminen vuodenajoittain

            season_defs = [
            {"name": "Talvi",  "start": "12-01", "end": "02-28", "type": "season"},
            {"name": "Kevät",  "start": "03-01", "end": "05-31", "type": "season"},
            {"name": "Kesä",   "start": "06-01", "end": "08-31", "type": "season"},
            {"name": "Syksy",  "start": "09-01", "end": "11-30", "type": "season"},
            ]

            seasonal_stats = {}

            # Copy your default seasons
            season_defs_copy = season_defs.copy()

            ## Jos käyttäjä on määritellyt oman aikavälin, lisätään se season_defs_copy listaan, jotta voidaan laskea min ja max myös sille aikavälille
            ## Käyttäjän määrittelemä aikaväli ei siis korvaa oletuksena olevia vuodenaikajaksoja, vaan se lisätään niiden rinnalle uutena jaksona, jolle lasketaan min ja max erikseen

            if self.custom_range_var.get():   # Checkbox ticked
                start_mmdd = self.custom_start_var.get()
                end_mmdd   = self.custom_end_var.get()
                # Convert MM-DD to "D.M." format
                start_day, start_month = start_mmdd.split("-")
                end_day, end_month     = end_mmdd.split("-")

                name = f"{int(start_day)}.{int(start_month)}. - {int(end_day)}.{int(end_month)}."
                # Append to the season_defs_copy list
                season_defs_copy.append({
                    "name": name,
                    "start": start_mmdd,
                    "end": end_mmdd,
                    "type": "custom"
                })

            seasonal_stats = {}

            df['mmdd']  = pd.to_datetime(df['Aika']).dt.strftime("%m-%d")

            ## minimin ja maksimin laskeminen käyttäjän määrittelemälle ajanjaksolle sekä oletuksena oleville vuodenaikajaksoille. Käytetään apuna filter_mmdd funktiota,
            #  joka suodattaa datan halutulle mm-dd välille riippumatta siitä minkä vuoden havainto on kyseessä. 
            #  Näin voidaan laskea min ja max esimerkiksi kaikille havainnoille, jotka on tehty 1.3-31.5 välisenä aikana riippumatta siitä onko havainto vuodelta 2024 vai 2020.

            for season_dict in season_defs_copy:
                season = season_dict["name"]
                start = season_dict["start"]
                end = season_dict["end"]
                
                df_season = self.filter_mmdd(df, start, end)
                
                if not df_season.empty:
                    seasonal_stats[f"{season}_Min"] = df_season[variable_name].min() * 0.01
                    seasonal_stats[f"{season}_Max"] = df_season[variable_name].max() * 0.01
                else:
                    seasonal_stats[f"{season}_Min"] = None
                    seasonal_stats[f"{season}_Max"] = None


            # --- Koko haetun aikasarjan tallentaminen  allekkain---
            if self.tallennus_var.get():
                if not self.save_path1:
                    messagebox.showerror("Polku puuttuu","Valitse tallennuspolku alkuperäiselle datalle ensin")
                    return
                df.to_excel(self.save_path1, index=False)
                with pd.ExcelWriter(self.save_path1, engine='openpyxl', mode='a') as writer:
                    stats_df.to_excel(writer, sheet_name='ylialavedet', index=False)
                self.status_text_var.set(f"Alkuperäinen data tallennettu: {self.save_path1}")

            # --- datan pivotointi vuosisarakkeisiin pivot_ja_tallennus function avulla. ---
            df_pivot = pivot_ja_tallennus(df, havainto_paikka=variable_name, vakio=0.01)
            # Valitaan vuosisarakkeet erikseen, jotta voidaan käyttää niitä myöhemmin pysyvyyksien laskennassa. Vuosi-sarakkeet tunnistetaan get_year_columns funktiolla, joka hakee kaikki sarakkeet joiden nimi on nelinumeroinen luku (eli vuosi)
            vuosi_sarakkeet = self.get_year_columns(df_pivot)
            if self.pivot_var.get():
                if self.prosentti_var.get():
                    df_pivot = prosentti_pisteet(df_pivot)
                if not self.save_path:
                    messagebox.showerror("Polku puuttuu","Valitse tallennuspolku pivot-tiedolle ensin")
                    return
                df_pivot.to_excel(self.save_path,index=False)
                with pd.ExcelWriter(self.save_path, engine='openpyxl', mode='a') as writer:
                    df.to_excel(writer, sheet_name='alkuperäinen data', index=False)
                    stats_df.to_excel(writer, sheet_name='ylialavedet', index=False)
                if self.pysyvyydet_var.get():
                    dataframe2 = pysyvyydet(df_pivot,vuosi_sarakkeet=vuosi_sarakkeet, step=0.10)
                    with pd.ExcelWriter(self.save_path, engine='openpyxl', mode='a') as writer:
                        dataframe2.to_excel(writer, sheet_name='Pysyvyys', index=False)
                if self.prosentti_var.get():
                    linechart(self.save_path, otsikko=" ", y_axis="vedenkorkeus", num=11)
                else:
                    linechart(self.save_path, otsikko=" ", y_axis="vedenkorkeus", num=4)

            # --- Interaktiivisen DASH sivun avaaminen ---
            launch_plot = messagebox.askyesno("Plot","Haluatko avata interaktiivisen kuvaajan vedenkorkeuksista?")
            if launch_plot:
                rajat_df = None
                ## Kysytään käyttäjältä haluaako hän lisätä kuvaajaan säännöstelyrajat. Säännöstelyrajat tulee olla excel-tiedostossa oikeassa muodossa.
                ## Jos tiedostoa ei anneta kuvaaja tehdään ilman rajoja.
                add_rajat = messagebox.askyesno("Säännöstelyrajat","Haluatko lisätä säännöstelyrajat kuvaajaan?")
                if add_rajat:
                    rajat_df, lisätieto_str = self.load_saadostelyrajat()
                    if rajat_df is None:
                        print("Rajojen lataus peruttu")
                        messagebox.showwarning(
                        "Cancelled",
                        "Rajoja ei lisätty, koska tiedoston valinta peruttiin. Luodaan kuvaaja ilman säännöstelyrajoja")
                        threading.Thread(target=self.run_hydrograph, args=(df,df_pivot[['Date','Min','Max','keskiarvo']], self.station_var.get(), variable_name, stats_df, seasonal_stats, season_defs_copy), daemon=True).start()
                    else:
                        messagebox.showwarning("rajat lisätty","Säännöstelyrajat lisätty kuvaajaan")  
                        print(rajat_df.head())
                        print(lisätieto_str)
                        threading.Thread(target=self.run_hydrograph, args=(df, df_pivot[['Date','Min','Max','keskiarvo']], self.station_var.get(), variable_name, stats_df,seasonal_stats, season_defs_copy, rajat_df, lisätieto_str), daemon=True).start()
                else:
                    threading.Thread(target=self.run_hydrograph, args=(df,df_pivot[['Date','Min','Max','keskiarvo']],self.station_var.get(), variable_name, stats_df,seasonal_stats, season_defs_copy), daemon=True).start()

            self.status_text_var.set("Valmis")
        except Exception as e:
            messagebox.showerror("Virhe", str(e))
            self.status_text_var.set("Idle")

    # ---------------- SUPPORTING FUNCTIONS ----------------

    ## Säännöstelyrajojen lataaminen Excel-tiedostosta. Tiedoston tulee olla oikeassa muodossa, muuten funktio kaatuu. Katso oikea muoto esimerkki-tiedostosta.
    def load_saadostelyrajat(self):
        path = filedialog.askopenfilename(title="Valitse säännöstelyrajat Excel tiedosto", filetypes=[("Excel files","*.xlsx")])
        if not path: return None, None
        print("Ladataan säännöstelyrajat tiedostosta:")
        df_rajat = pd.read_excel(path)
        df_rajat[['alaraja','yläraja']] = df_rajat[['alaraja','yläraja']].astype(float) * 0.01
        df_rajat['Päivä'] = pd.to_datetime(df_rajat['Päivä'], format="%d.%m.")
        df_rajat['Päivä'] = pd.to_datetime(df_rajat['Päivä'].dt.strftime('%d.%m.') + '2000', format='%d.%m.%Y')

        # Check if 'lisätieto' column exists and store the first row
        lisätieto_str = None
        if 'lisätieto' in df_rajat.columns:
            lisätieto_str = str(df_rajat.loc[0, 'lisätieto'])

        df_rajat1 = df_rajat[['Päivä','alaraja','yläraja']].copy()
        
        return df_rajat1, lisätieto_str

    ## Apufunktio, joka käynnistää interaktiivisen hydrograafin selaimessa. Hydrograafi on toteutettu erikseen tiedostossa Hydrograafi.py.
    def run_hydrograph(self, df, df_pivot, station_name, level_name, stats_df = None, seasonal_stats = None, season_defs=None, rajat_df=None, lisätieto_str=None):
        import Hydrograafi
        import webbrowser

        app = Hydrograafi.init_dash(df, level_name, df_pivot, station_name, stats_df, seasonal_stats, season_defs, rajat_df, lisätieto_str)
        # Force open browser
        port = self.find_free_port()
        webbrowser.open(f"http://127.0.0.1:{port}")
        app.run(debug=False, use_reloader=False, port=port)

    ## Apufunktio, joka suodattaa datan halutulle mm-dd välille riippumatta siitä minkä vuoden havainto on kyseessä. Näin voidaan laskea min ja max esimerkiksi kaikille havainnoille, jotka on tehty 1.3-31.5 välisenä aikana riippumatta siitä onko havainto vuodelta 2024 vai 2020.
    def filter_mmdd(self, df, start_mmdd, end_mmdd):
        mmdd = df['mmdd']
        if start_mmdd <= end_mmdd:
            return df[(mmdd >= start_mmdd) & (mmdd <= end_mmdd)]
        else:  # wraps over year end
            return df[(mmdd >= start_mmdd) | (mmdd <= end_mmdd)]

    ## Apufunktio, joka etsii vapaan portin Dash-sovellukselle, jotta voidaan varmistaa että sovellus käynnistyy onnistuneesti ilman porttikonflikteja. Tämä on erityisen tärkeää, jos käyttäjällä on muita sovelluksia jotka käyttävät samoja portteja.
    def find_free_port(self):
        s = socket.socket()
        s.bind(('', 0))  # bind to a free port
        port = s.getsockname()[1]
        s.close()
        return port
    
    ## Apufunktio, joka palauttaa DataFramen sarakkeet, jotka edustavat vuosia, vaikka ne olisivatkin merkkijonoja kuten '2000'.
    def get_year_columns(self, df):
        """Return columns that represent years, even if they are strings like '2000'."""
        year_cols = []
        for col in df.columns:
            try:
                # Try converting column name to int
                year = int(col)
                if 1900 <= year <= 2100:  # sanity check for valid year
                    year_cols.append(col)
            except (ValueError, TypeError):
                continue
        return year_cols



# ---------------- MAIN ----------------
def main():
    root = tk.Tk()
    root.title("Hydrologiset työkalut")
    root.geometry("460x540")

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    vedenkorkeus = VedenkorkeusTab(notebook)
    notebook.add(vedenkorkeus.frame, text="Vedenkorkeus")

    root.mainloop()

if __name__ == "__main__":
    main()
