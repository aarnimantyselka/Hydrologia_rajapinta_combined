import tkinter as tk
from tkinter import ttk
import pandas as pd

# Import your existing tabs
from Lumenvesiarvo_tab import LumenvesiarvoTab
from vedenkorkeus_tab import VedenkorkeusTab
from virtaama_tab import VirtaamaTab
from combined_tab import CombinedTab  # <-- Our new tab


class HydroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hydrologinen työkalu")
        self.root.geometry("600x800")  # Adjust window size as needed

        # Main notebook
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

                # ---- Load shared data ONCE ----
        self.vk_stations = pd.read_csv(
            "Vedenkorkeusasemat_kaikki_utf8.csv",
            sep=";",
            encoding="utf-8"
        )

        self.va_stations = pd.read_csv(
            "Virtaama_asemat_kaikki.csv",
            sep=";",
            encoding="utf-8"
        )
        self.SA_stations = pd.read_csv(
            "Lumenvesiarvo_alueet.csv",
            sep=";",
            encoding="utf-8",
            dtype={"Tunnus": str}  # <-- read Tunnus as string
        )

        # Build tabs
        self.build_tabs()

    def build_tabs(self):
        # ---------------------------
        # Vedenkorkeus tab
        # ---------------------------
        self.vedenkorkeus_tab = VedenkorkeusTab(self.notebook, stations_df=self.vk_stations)
        self.notebook.add(self.vedenkorkeus_tab.frame, text="Vedenkorkeus")

        # ---------------------------
        # Virtaama tab
        # ---------------------------
        self.virtaama_tab = VirtaamaTab(self.notebook, stations_df=self.va_stations)
        self.notebook.add(self.virtaama_tab.frame, text="Virtaama")

        # ---------------------------
        # Lumenvesiarvo tab
        # ---------------------------
        self.lumenvesiarvo_tab = LumenvesiarvoTab(self.notebook, stations_df=self.SA_stations)
        self.notebook.add(self.lumenvesiarvo_tab.frame, text="Lumenvesiarvo")

        # ---------------------------
        # Combined tab
        # ---------------------------
        self.combined_tab = CombinedTab(self.notebook, vk_stations_df=self.vk_stations, va_stations_df=self.va_stations)
        self.notebook.add(self.combined_tab.frame, text="Combined VK + VA")


def main():
    root = tk.Tk()
    app = HydroApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

