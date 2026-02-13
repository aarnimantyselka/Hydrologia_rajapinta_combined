import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import pandas as pd
import threading
import webbrowser
import os

import Hydrograafi_virtaama
from python_vesla import Lumen_aluevesiarvo_API, pivot_ja_tallennus, prosentti_pisteet


class LumenvesiarvoTab:
    def __init__(self, parent, stations_df):
        self.parent = parent
        self.frame = ttk.Frame(parent)
        self.stations_df = stations_df  # <-- Now we receive the stations dataframe from outside
        # ---------------- Variables ----------------
        self.station_var = tk.StringVar()
        self.maakunta_var = tk.StringVar(value="All")
        self.viimeisin_2026_var = tk.BooleanVar()
        self.tallennus_var = tk.BooleanVar()
        self.pivot_var = tk.BooleanVar()
        self.prosentti_var = tk.BooleanVar()
        self.pysyvyydet_var = tk.BooleanVar()

        self.save_path = None
        self.save_path1 = None
        self.save_path_var = tk.StringVar(value="Pivotoidun datan tallennuspolku: ei valittu")
        self.save_path1_var = tk.StringVar(value="Muuttumattoman datan tallennuspolku: ei valittu")

        self.status_var = tk.StringVar(value="Idle")
        self.first_obs_var = tk.StringVar(value="Ensimmäinen havainto: –")
        self.last_obs_var = tk.StringVar(value="Viimeisin havainto: –")

        self.stations_df["display"] = (self.stations_df["Nimi"].astype(str) + " - " + self.stations_df["Tunnus"].astype(str))

        self.station_lookup = {row.display: row for row in self.stations_df.itertuples()}
        self.display_to_id = dict(zip(self.stations_df["display"], self.stations_df["Tunnus"]))
        self.search_index = {
            f"{row.Tunnus} {row.Nimi}".lower(): row.Tunnus
            for row in self.stations_df.itertuples()
        }

        maakunnat = sorted(self.stations_df["Maakunta"].dropna().unique().tolist())
        maakunnat.insert(0, "All")
        self.maakunnat = maakunnat

        self.build_gui()

    # ---------------- GUI ----------------
    def build_gui(self):

        # --- INTERNAL NOTEBOOK (inside Virtaama tab) ---
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
        # SCROLL CONTAINER
        # ===============================
        container = ttk.Frame(main_frame)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)

        scrollable = ttk.Frame(canvas)
        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ===============================
        # MAAKUNTA
        # ===============================
        tk.Label(scrollable, text="Maakunta").pack(anchor="w", padx=10, pady=(8, 0))

        row = tk.Frame(scrollable)
        row.pack(anchor="w", padx=10)

        # Bind the Maakunta combobox
        self.maakunta_combo = ttk.Combobox(
            row,
            textvariable=self.maakunta_var,
            values=self.maakunnat,
            state="readonly",
            width=30
        )
        self.maakunta_combo.pack(side="left")
        self.maakunta_combo.bind("<<ComboboxSelected>>", lambda e: self.filter_stations())

        tk.Checkbutton(
            row,
            text="Viimeisin havainto 2026",
            variable=self.viimeisin_2026_var,
            command=self.filter_stations
        ).pack(side="left", padx=15)



        # ===============================
        # ASEMA
        # ===============================
        tk.Label(scrollable, text="Valitse havaintoasema").pack(anchor="w", padx=10)

        self.station_combo = ttk.Combobox(
            scrollable,
            textvariable=self.station_var,
            values=self.stations_df["display"].tolist(),
            width=30
        )
        self.station_combo.pack(anchor="w", padx=10)

        self.station_combo.bind("<KeyRelease>", lambda e: self.filter_stations())
        self.station_combo.bind("<<ComboboxSelected>>", self.on_station_selected)

        tk.Label(scrollable, textvariable=self.first_obs_var).pack(anchor="w", padx=10)
        tk.Label(scrollable, textvariable=self.last_obs_var).pack(anchor="w", padx=10)

        # ===============================
        # AIKAVÄLI
        # ===============================
        date_row = tk.Frame(scrollable)
        date_row.pack(anchor="w", padx=10, pady=8)

        self.start_entry = tk.Entry(date_row, width=12)
        self.start_entry.insert(0, "2020-01-01")
        self.start_entry.pack(side="left")

        self.end_entry = tk.Entry(date_row, width=12)
        self.end_entry.insert(0, "2025-12-10")
        self.end_entry.pack(side="left", padx=20)

        # ===============================
        # TALLENNUS + AJO
        # ===============================
        self.create_save_options(scrollable)

        tk.Button(
            scrollable,
            text="Run",
            width=20,
            command=self.run_analysis
        ).pack(anchor="w", padx=10, pady=15)

        tk.Label(
            scrollable,
            textvariable=self.status_var,
            fg="blue"
        ).pack()

        # ===============================
        # METADATA
        # ===============================
        self.create_metadata_tab(metadata_frame)


        # ---------------- Actions ----------------
    def filter_stations(self):
        typed = self.station_var.get().lower() if self.station_var.get() else ""
        df_filtered = self.stations_df.copy()

        # Filter by ViimeisinHavainto 2026
        if self.viimeisin_2026_var.get():
            df_filtered = df_filtered[pd.to_datetime(df_filtered["ViimeisinHavainto"], errors='coerce').dt.year == 2026]

        # Filter by Maakunta
        if self.maakunta_var.get() != "All":
            df_filtered = df_filtered[df_filtered["Maakunta"] == self.maakunta_var.get()]

        # Filter by typed text in the combobox
        if typed:
            df_filtered = df_filtered[df_filtered["display"].str.lower().str.contains(typed)]

        new_values = sorted(df_filtered["display"].tolist())
        self.station_combo["values"] = new_values

        # Reset first/last observation if typed text doesn't match any station
        if typed and self.station_var.get() not in new_values:
            self.first_obs_var.set("Ensimmäinen havainto: –")
            self.last_obs_var.set("Viimeisin havainto: –")

        self.station_combo.update()



    def on_station_selected(self, event=None):
        station = self.station_lookup.get(self.station_var.get())
        if not station:
            self.first_obs_var.set("Ensimmäinen havainto: –")
            self.last_obs_var.set("Viimeisin havainto: –")
            return
        self.first_obs_var.set(f"Ensimmäinen havainto: {station.EnsimmainenHavainto}")
        self.last_obs_var.set(f"Viimeisin havainto: {station.ViimeisinHavainto}")

    def select_original_path(self):
        self.save_path1 = filedialog.asksaveasfilename(defaultextension=".xlsx")
        if self.save_path1:
            self.save_path1_var.set(self.save_path1)

    def select_pivot_path(self):
        self.save_path = filedialog.asksaveasfilename(defaultextension=".xlsx")
        if self.save_path:
            self.save_path_var.set(self.save_path)

    def run_analysis(self):
        try:
            station_id = self.resolve_station_id()
            start = self.start_entry.get()
            end = self.end_entry.get()

            datetime.strptime(start, "%Y-%m-%d")
            datetime.strptime(end, "%Y-%m-%d")

            self.status_var.set("Haetaan dataa...")
            self.frame.update_idletasks()

            df = Lumen_aluevesiarvo_API(start, end, station_id)
            if df.empty:
                raise ValueError("Ei dataa")

            variable = "Arvo"
            print(df.iloc[:,1].head())
            quit()
            df_pivot = pivot_ja_tallennus(df, havainto_paikka=variable, vakio= 1.0)

            self.launch_plot(df, df_pivot)

            self.status_var.set("Valmis")

        except Exception as e:
            messagebox.showerror("Virhe", str(e))
            self.status_var.set("Idle")

    def resolve_station_id(self):
        sel = self.station_var.get()
        if sel in self.display_to_id:
            return self.display_to_id[sel]
        for k, v in self.search_index.items():
            if sel.lower() in k:
                return v
        raise ValueError("Asemaa ei löytynyt")

    def launch_plot(self, df, df_pivot):
        if not messagebox.askyesno("Plot", "Avaa interaktiivinen kuvaaja?"):
            return
        threading.Thread(
            target=self.run_hydrograph,
            args=(df, df_pivot[['Date', 'Min', 'Max', 'keskiarvo']]),
            daemon=True
        ).start()

    def run_hydrograph(self, df, min_max_ka):
        app = Hydrograafi_virtaama.init_dash(df, "Arvo", min_max_ka)
        webbrowser.open("http://127.0.0.1:8050")
        app.run(debug=False, use_reloader=False)

    # ---------------- UI helpers ----------------
    def create_save_options(self, parent):
        tk.Checkbutton(parent, text="Tallenna alkuperäinen", variable=self.tallennus_var)\
            .pack(anchor="w", padx=10)
        tk.Button(parent, text="Valitse polku", command=self.select_original_path)\
            .pack(anchor="w", padx=10)
        tk.Label(parent, textvariable=self.save_path1_var, fg="gray").pack(anchor="w", padx=10)

        tk.Checkbutton(parent, text="Pivotointi", variable=self.pivot_var)\
            .pack(anchor="w", padx=10)
        tk.Button(parent, text="Valitse pivot-polku", command=self.select_pivot_path)\
            .pack(anchor="w", padx=10)
        tk.Label(parent, textvariable=self.save_path_var, fg="gray").pack(anchor="w", padx=10)

    def create_metadata_tab(self, parent):
        text = tk.Text(parent, wrap="word")
        text.pack(fill="both", expand=True)
        text.insert("end", "Virtaama työkalun ohjeet...")
        text.configure(state="disabled")


