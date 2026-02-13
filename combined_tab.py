import tkinter as tk
from tkinter import ttk, messagebox
import threading
import webbrowser
import pandas as pd
from datetime import datetime

from python_vesla import vedenkorkeus_API, pivot_ja_tallennus  # Existing functions
from python_vesla_virtaama import vedenkorkeus_API as virtaama_API  # Adjust if different
from combined_dash import init_combined_dash  # The Dash function we just wrote


class CombinedTab:
    def __init__(self, parent, vk_stations_df, va_stations_df):
        self.parent = parent
        self.frame = ttk.Frame(parent)
        self.vk_stations = vk_stations_df
        self.va_stations = va_stations_df
        # Variables
        self.vk_station_var = tk.StringVar()
        self.va_station_var = tk.StringVar()
        self.start_var = tk.StringVar(value="2020-01-01")
        self.end_var = tk.StringVar(value="2025-12-10")

        self.status_var = tk.StringVar(value="Idle")

        # --- Vedenkorkeusasemien lataaminen ---
        self.vk_stations["display"] = (self.vk_stations["Nimi"].astype(str) + " - " + self.vk_stations["Tunnus"].astype(str))
        self.va_stations["display"] = (self.va_stations["Nimi"].astype(str) + " - " + self.va_stations["Tunnus"].astype(str))

        # --- Sort stations alphabetically by display ---
        self.vk_stations = self.vk_stations.sort_values("display")
        self.va_stations = self.va_stations.sort_values("display")

        # --- Lookups ---
        self.vk_display_to_id = dict(
            zip(self.vk_stations["display"], self.vk_stations["Tunnus"])
        )
        self.va_display_to_id = dict(
            zip(self.va_stations["display"], self.va_stations["Tunnus"])
        )


        self.build_gui()

    def build_gui(self):
        scrollable = ttk.Frame(self.frame)
        scrollable.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Vedenkorkeus station ---
        tk.Label(scrollable, text="Valitse vedenkorkeusasema:").pack(anchor="w")
        self.vk_combo = ttk.Combobox(
            scrollable,
            textvariable=self.vk_station_var,
            values=self.vk_stations["display"].tolist(),
            width=40,
        )
        self.vk_combo.pack(anchor="w", pady=5)
        self.vk_combo.bind("<KeyRelease>", lambda e: self.filter_vk_stations())

        # --- Virtaama station ---
        tk.Label(scrollable, text="Valitse virtaama-asema:").pack(anchor="w")
        self.va_combo = ttk.Combobox(
            scrollable,
            textvariable=self.va_station_var,
            values=self.va_stations["display"].tolist(),
            width=40,
        )
        self.va_combo.pack(anchor="w", pady=5)
        self.va_combo.bind("<KeyRelease>", lambda e: self.filter_va_stations())

        # --- Date range ---
        date_frame = tk.Frame(scrollable)
        date_frame.pack(anchor="w", pady=8)
        tk.Label(date_frame, text="Alku:").pack(side="left")
        tk.Entry(date_frame, textvariable=self.start_var, width=12).pack(side="left", padx=5)
        tk.Label(date_frame, text="Loppu:").pack(side="left")
        tk.Entry(date_frame, textvariable=self.end_var, width=12).pack(side="left", padx=5)

        # --- Run button ---
        tk.Button(
            scrollable, text="Run", width=20, command=self.run_combined
        ).pack(anchor="w", pady=10)

        # Status label
        tk.Label(scrollable, textvariable=self.status_var, fg="blue").pack(anchor="w", pady=5)

    def filter_vk_stations(self):
        typed = self.vk_station_var.get().lower()
        df = self.vk_stations

        if typed:
            df = df[df["display"].str.lower().str.contains(typed)]

        self.vk_combo["values"] = df["display"].tolist()


    def filter_va_stations(self):
        typed = self.va_station_var.get().lower()
        df = self.va_stations

        if typed:
            df = df[df["display"].str.lower().str.contains(typed)]

        self.va_combo["values"] = df["display"].tolist()

    def run_combined(self):
        try:
            vk_station = self.vk_station_var.get()
            va_station = self.va_station_var.get()
            start = self.start_var.get()
            end = self.end_var.get()

            # Validate dates
            datetime.strptime(start, "%Y-%m-%d")
            datetime.strptime(end, "%Y-%m-%d")

            if not vk_station or not va_station:
                raise ValueError("Valitse molemmat asemat.")

            self.status_var.set("Haetaan dataa...")
            self.frame.update()

            # Fetch data in a separate thread to avoid freezing GUI
            threading.Thread(target=self.fetch_and_plot, args=(vk_station, va_station, start, end), daemon=True).start()

        except Exception as e:
            messagebox.showerror("Virhe", str(e))
            self.status_var.set("Idle")

    def fetch_and_plot(self, vk_station, va_station, start, end):
        try:
            # --- Fetch vedenkorkeus ---
            vk_id = self.vk_display_to_id.get(vk_station)
            va_id = self.va_display_to_id.get(va_station)

            if not vk_id or not va_id:
                raise ValueError("Asemaa ei löytynyt.")
            vk_df = vedenkorkeus_API(start, end, vk_id)

            # --- Fetch virtaama ---
            va_df = virtaama_API(start, end, va_id)  # adjust function as needed

            # Optional: min/max/avg for vedenkorkeus
            vk_min_max = pivot_ja_tallennus(vk_df, havainto_paikka="Arvo", vakio=0.01)
            # Drop rows where 'Date' is not a valid date
            vk_min_max = vk_min_max[pd.to_datetime(vk_min_max['Date'], errors='coerce').notna()]

            va_df.rename(columns={"Aika": "Date"}, inplace=True)
            vk_df.rename(columns={"Aika": "Date"}, inplace=True)
            self.status_var.set("Avataan kuvaaja...")

            app = init_combined_dash(vk_df, va_df, vk_min_max)
            webbrowser.open("http://127.0.0.1:8050")
            app.run(debug=False, use_reloader=False)

            self.status_var.set("Valmis")
        except Exception as e:
            self.status_var.set("Idle")
            messagebox.showerror("Virhe", str(e))
