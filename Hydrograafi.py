import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State

import pandas as pd

import plotly.graph_objects as go
from plotly.subplots import make_subplots

## Tiedosto jonka avulla luodaan interaktiivinen kuvaaja ja tunnuslukutaulukot vedenkorkeuksista Dash-kirjaston avulla

def init_dash(dataframe, variable_name, min_max_ka,tunnus_nimi, stats_df = None, seasonal_stats = None, season_defs=None, rajat_df = None, lisätieto_str = None):

    app = dash.Dash(__name__)
    
    ## Kursorin tyylin vaihtaminen kuvaajassa
    app.index_string = '''
        <!DOCTYPE html>
        <html>
            <head>
                {%metas%}
                <title>{%title%}</title>
                {%favicon%}
                {%css%}
                <style>
                    .js-plotly-plot .plotly .svg-container,
                    .js-plotly-plot .plotly .main-svg,
                    .js-plotly-plot .plotly .nsewdrag,
                    .js-plotly-plot .plotly .cursor-crosshair,
                    .js-plotly-plot .plotly .cursor-ew-resize,
                    .js-plotly-plot .plotly .drag {
                        cursor: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><circle cx="10" cy="10" r="3" fill="red"/></svg>'), auto !important;
                    }
                </style>
            </head>
            <body>
                {%app_entry%}
                <footer>
                    {%config%}
                    {%scripts%}
                    {%renderer%}
                </footer>
            </body>
        </html>
        '''
    ## Sivun asettelu
    app.layout = html.Div([
        html.H2("Vedenkorkeusarvojen visualoisointi"),    
        dcc.Store(id='data-store', data = dataframe.to_dict('records')),
        dcc.Store(id='clicked-lines', data=[]),
        dcc.Store(id='variable-names', data=variable_name),
        dcc.Store(id="min-max-ka", data = min_max_ka.to_dict('records')),
        dcc.Store(id="rajat", data = rajat_df.to_dict('records') if rajat_df is not None else None),   
        dcc.Store(id ='tunnus-nimi', data = tunnus_nimi),
        dcc.Store(id='lisätieto-store', data = lisätieto_str),  # Hidden div for triggering callbacks if needed
        dcc.Store(id='stats-store', data=stats_df.to_dict('records') if stats_df is not None else None),
        dcc.Store(id='season-store', data=seasonal_stats if seasonal_stats is not None else None),
        dcc.Store(id='season-defs-store', data=season_defs if season_defs is not None else None),


        # Dropdown-valikko vuosille
        dcc.Dropdown(
            id='year-dropdown',
            options=[{'label': y, 'value': y} for y in dataframe['Vuosi'].unique()],
            value=dataframe['Vuosi'].unique()[0],
            multi=True  # oletusvuosi
        ),


        html.Div(
            [
                html.Button("Clear lines", id='clear-lines', n_clicks=0),

                dcc.Checklist(
                    id="allow-2-years",
                    options=[{"label": "Salli 2 vuotta", "value": "yes"}],
                    value=[],  # unchecked by default
                    style={"marginLeft": "16px", "fontSize": "16px"},
                    inputStyle={"marginRight": "6px"}
                ),

                # --- Hovermode toggle ---
                dcc.Checklist(
                    id='hovermode-toggle',
                    options=[{"label": "Enable hovermode", "value": "on"}],
                    value=["on"],  # enabled by default
                    style={"marginLeft": "16px", "fontSize": "16px"},
                    inputStyle={"marginRight": "6px"}
                ),
            ],
            style={"marginTop": "8px", "display": "flex", "alignItems": "center"}
        ),
        ## Kuvaaja ja tilastot vierekkäin
        html.Div(
            [
                dcc.Graph(
                    id='hydro-graph',
                    style={'flex': '3'}
                ),

                html.Div(
                    id='stats-panel',
                    style={
                        'flex': '1',
                        'padding': '12px',
                        'borderLeft': '1px solid #ccc',
                        'fontSize': '16px'
                    }
                )
            ],
            style={'display': 'flex', 'alignItems': 'flex-start'}
        ),
        ## Mahdolliset säännöstelyrajojen lisätiedot kuvaajan alla
        html.Div(
        id='lisätieto-div',
        children=lisätieto_str if lisätieto_str else "",
        style={'marginTop': '3px', 'fontStyle': 'italic', 'color': 'black', 'fontSize': '20px'}
    )

    ])

    # --- Muuttumattomat y-akselin rajat (lasketaan kerran alussa) ---
    var_min = dataframe[variable_name].min()
    var_max = dataframe[variable_name].max()

    if rajat_df is not None and not rajat_df.empty:
        rajat_min = rajat_df['alaraja'].min()
        rajat_max = rajat_df['yläraja'].max()
        
        # Otetaan aikasarjan suurin ja pienin arvo huomioon, jotta kaikki data mahtuu kuvaajaan
        y_primary_min = min(var_min, rajat_min)
        y_primary_max = max(var_max, rajat_max)
    else:
        y_primary_min = var_min
        y_primary_max = var_max

        # Lisätään pieni marginaali y-akselin rajoihin, jotta data ei ole kiinni reunoissa
    pad_primary = 0.05 * (y_primary_max - y_primary_min)
    y_primary_range = [y_primary_min - pad_primary, y_primary_max + pad_primary]


    # Callback, joka päivittää kuvaajan
    @app.callback(
        Output('hydro-graph', 'figure'),
        Output('clicked-lines', 'data'),
        Input('year-dropdown', 'value'),
        Input('hydro-graph', 'clickData'),
        Input('clear-lines', 'n_clicks'),
        State('clicked-lines', 'data'),
        Input('hovermode-toggle', 'value'),
        State('data-store', 'data'),
        State('variable-names','data'),
        State('min-max-ka', 'data'),
        State('rajat', 'data'),
        State('tunnus-nimi', 'data')
    )

    ## Funktio joka päivittää kuvaajan valittujen vuosien, klikkaustiedon, hovermode-asetuksen ja muiden tietojen perusteella.
    def update_graph(selected_years,clickData, clear_nclicks, clicked_lines, hovermode_value, data, variable_name, min_max_ka, rajat, tunnus_nimi):
        # Suodata valittu vuosi
        df = pd.DataFrame(data)

        # ALWAYS make selected_years a list
        if selected_years is None:
            selected_years = []
        elif not isinstance(selected_years, list):
            selected_years = [selected_years]

        df_years = df[df['Vuosi'].isin(selected_years)].copy()
        min_max_ka_df = pd.DataFrame(min_max_ka)
        
        vanhin_vuosi = df['Vuosi'].min()
        uusin_vuosi = df['Vuosi'].max()
        year_range_label = f"({vanhin_vuosi}-{uusin_vuosi})"
        # Create subplot with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
                            
        
        # lisää min max ja keskiarvo
        min_max_ka_df['Date'] = pd.to_datetime(min_max_ka_df['Date'], errors='coerce')
        # Drop rows where Date is not a real date (NaT)
        min_max_ka_df = min_max_ka_df.dropna(subset=['Date'])
        min_max_ka_df = min_max_ka_df[~((min_max_ka_df['Date'].dt.month == 2) &(min_max_ka_df['Date'].dt.day == 29))]

        """
        fig.add_trace(
            go.Scatter(x=min_max_ka_df['Date'], y=min_max_ka_df['Min'].interpolate(),
                    name=f"Min {year_range_label}",mode='lines', line=dict(width=2, color='blue', dash = 'dash'), visible='legendonly'),
            secondary_y=False
        )

        fig.add_trace(
            go.Scatter(x=min_max_ka_df['Date'], y=min_max_ka_df['Max'].interpolate(),
                    name=f"Max {year_range_label}",mode='lines', line=dict(width=2, color='red', dash = 'dash'), visible='legendonly'),
            secondary_y=False
        )
        """
        # --- Luodaan maalattu alue minimin ja maksimin väliin  ---
        fig.add_trace(
            go.Scatter(
                x=min_max_ka_df['Date'],
                y=min_max_ka_df['Min'].interpolate(),
                mode='lines',
                line=dict(
                    width=0.8,                       # very thin
                    color='rgba(160,160,160,0.9)'    # neutral grey
                ),
                name=f"Min–Max {year_range_label}",
                legendgroup="minmax",
                showlegend=True,                   # ← only legend item
                hovertemplate=(
                "Min: %{y:.2f} m"
                "<extra></extra>"
                )
            ),
            secondary_y=False
        )
        ## Luodaan maksimin kohdalle samaan kohtaan toinen Scatter, joka piirtää minimin ja maksimin väliin maalatun alueen. Tämä toinen Scatter on asetettu ilman legendaa ja sen hovertemplate näyttää vain maksimin arvon.
        fig.add_trace(
            go.Scatter(
                x=min_max_ka_df['Date'],
                y=min_max_ka_df['Max'].interpolate(),
                mode='lines',
                line=dict(
                    width=0.8,                       # same thin line
                    color='rgba(160,160,160,0.9)'
                ),
                fill='tonexty',
                fillcolor='rgba(180,180,180,0.30)', # soft grey area
                legendgroup="minmax",
                showlegend=False,                  # ← hidden
                hovertemplate=(
                "Max: %{y:.2f} m"
                "<extra></extra>"
                )
            ),
            secondary_y=False
        )

        ## luodaan keskiarvon viivan, joka on harmaa katkoviiva ja näkyy koko ajan.
        fig.add_trace(
            go.Scatter(x=min_max_ka_df['Date'], 
                       y=min_max_ka_df['keskiarvo'].interpolate(),
                       name=f"Keskiarvo {year_range_label}",
                       mode='lines',
                       line=dict(width=2,  color='rgba(120,120,120,1)', dash = 'dash'),
                       hovertemplate=(
                        "Keskiarvo: %{y:.2f} m"
                        "<extra></extra>"
                        )),
            secondary_y=False
        )

        ## Luodaan eriväriset viivat valituille vuosille. Käytetään modulo-operaatiota värien kierrättämiseen, jotta saadaan eri värit, mutta ei liian räikeitä.
        colors = ['orange', 'green']  # colors for 2 years
        for i, year in enumerate(selected_years):
            df_y = df_years[df_years['Vuosi'] == year].copy()
            # Ensure Aika is datetime
            df_y['Aika'] = pd.to_datetime(df_y['Aika'], errors='coerce')

            # Remove leap day (Feb 29)
            df_y = df_y[~((df_y['Aika'].dt.month == 2) & (df_y['Aika'].dt.day == 29))]

            df_y['date_md'] = pd.to_datetime(df_y['Aika'].dt.strftime('%d.%m.') + '2000', format='%d.%m.%Y')
            
            fig.add_trace(
                go.Scatter(
                    x=df_y['date_md'],
                    y=df_y[variable_name],
                    name=str(year),
                    line=dict(color=colors[i % len(colors)]),
                    hovertemplate=(
                        str(year) + ": %{y:.2f} m"
                        "<extra></extra>"
                    )
                ),
                secondary_y=False
            )
        
        ## Tarkastetaan onko käyttäjä määritellyt säännöstelyrajoja ja lisätään ne kuvaajaan jos ne on määritelty.
        #  Interpoloidaan viivat säännöstelypisteiden mukaan.
        if rajat is not None:
            # rajat comes from dcc.Store as a list of dicts, need to reconstruct properly
            df_rajat = pd.DataFrame(rajat)
            
            # Re-convert Päivä to datetime (it's been serialized to string in dcc.Store)
            df_rajat['Päivä'] = pd.to_datetime(df_rajat['Päivä'])
            
            df_rajat['day_of_year'] = df_rajat['Päivä'].dt.dayofyear
            df_rajat = df_rajat.sort_values('day_of_year').reset_index(drop=True)
            
            # Create extended dataframe for circular interpolation
            # --- Circular interpolation  ---

            df_base = df_rajat[['day_of_year', 'alaraja', 'yläraja']].copy()
            df_base = df_base.sort_values('day_of_year')

            # Duplicate data for circular continuity
            df_plus = df_base.copy()
            df_plus['day_of_year'] += 365

            df_minus = df_base.copy()
            df_minus['day_of_year'] -= 365

            df_circular = pd.concat(
                [df_minus, df_base, df_plus],
                ignore_index=True
            ).sort_values('day_of_year')

            # Continuous index for interpolation
            full_range = pd.DataFrame({
                'day_of_year': range(
                    int(df_circular['day_of_year'].min()),
                    int(df_circular['day_of_year'].max()) + 1
                )
            })

            df_interp = full_range.merge(
                df_circular,
                on='day_of_year',
                how='left'
            )

            df_interp[['alaraja', 'yläraja']] = (
                df_interp[['alaraja', 'yläraja']]
                .interpolate(method='linear', limit_direction='both')
            )

            # Keep only real calendar year
            df_merged = df_interp[
                (df_interp['day_of_year'] >= 1) &
                (df_interp['day_of_year'] <= 365)
            ].reset_index(drop=True)

            # Convert back to dates
            df_merged['Päivä'] = pd.to_datetime(
                '2000' + df_merged['day_of_year'].astype(str),
                format='%Y%j'
            )
            
            # Plot the traces
            fig.add_trace(
                go.Scatter(
                    x=df_merged['Päivä'], 
                    y=df_merged['alaraja'],
                    name="Säännöstelyrajat",
                    legendgroup="säännöstelyrajat",
                    mode='lines',
                    line=dict(color='black'),
                    hoverinfo='skip'
                ),
                secondary_y=False
            )
            
            fig.add_trace(
                go.Scatter(
                    x=df_merged['Päivä'], 
                    y=df_merged['yläraja'],
                    name="Yläraja",
                    legendgroup="säännöstelyrajat",
                    showlegend=False,
                    mode='lines',
                    line=dict(color='black'),
                    hoverinfo='skip'
                ),
                secondary_y=False
            )
            
        if isinstance(tunnus_nimi, str) and " - " in tunnus_nimi:
            nimi, tunnus = tunnus_nimi.rsplit(" - ", 1)
            format = f"{nimi} ({tunnus})"
        else:
            format = tunnus_nimi
        num_years = len(selected_years)
        print(num_years)
        if num_years == 1:
            teksti = f"Vuoden {selected_years[0]} päiväkohtaiset vedenkorkeudet – {format}"
        if num_years == 2:
            teksti = f"Vuosien {selected_years[0]} ja {selected_years[1]} päiväkohtaiset vedenkorkeudet – {format}"


        ## Määritellään 'hover' -tiedon näyttöasetukset.
        ## Käyttäjä valitsee klikkaamalla haluaako hän nähdä tietoja vai ei.
        hovermode_setting = 'x unified' if 'on' in (hovermode_value or []) else False
        fig.update_layout(
        title_text=teksti,
        height = 800,
        width = 1200,
        hovermode=hovermode_setting,       
        legend=dict(orientation="v", yanchor="top", itemwidth=55, xanchor="right", x=1.2, traceorder="reversed", itemsizing='constant'), font=dict(size=14)
        )
        fig.update_xaxes(
            title_text="päivämäärä",
            showspikes=True,                   # Vertikaalinen viiva käytössä
            spikemode='across',
            spikesnap='cursor',
            spikecolor='gray',
            spikethickness=1,
            tickformat='%d.%m.',  # Date format for x-axis ticks
            dtick="M1"  # Monthly ticks
        )

        y_span = y_primary_range[1] - y_primary_range[0]

        if y_span <= 1:
            dtick = 0.1
        elif y_span <= 2:
            dtick = 0.25
        else:
            dtick = 0.5

        fig.update_yaxes(
        title_text=f"Vedenkorkeus {variable_name} (m)",
        secondary_y=False,
        range=y_primary_range,
        fixedrange=True,
        dtick = dtick
        )
        var_name0 = variable_name
        # Update axis titles
        fig.update_xaxes(title_text="Aika", range=[pd.to_datetime('2000-01-01'), pd.to_datetime('2000-12-31')])
        fig.update_yaxes(title_text=f"Vedenkorkeus {var_name0} (m)", secondary_y=False)

        # ---------- Käyttäjän on mahdollista tallentaa yksittäisen päivän arvoja kuvaajaan näkyville. Tässä kohtaa määritellään tämä toiminnallisuus ----------
        ctx = dash.callback_context
        trigger = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

        ## Käsitellään eri tapahtumat: 'clear-lines' painettu, 'year-dropdown' muuttunut tai kuvaajaa on klikattu
        if trigger == 'clear-lines':
            clicked_lines = []

        elif trigger == 'year-dropdown':
            clicked_lines = []

        elif clickData and 'points' in clickData and len(clickData['points']) > 0:
            x_clicked = clickData['points'][0].get('x')
            if x_clicked is not None:
                try:
                    xdt = pd.to_datetime(x_clicked)
                    x_iso = xdt.isoformat()

                    # Prevent duplicate lines at same date
                    if not any(d['x'] == x_iso for d in clicked_lines):

                        # Prepare annotation text for all selected years
                        texts = []

                        # --- Add selected year values FIRST ---
                        for year in selected_years:
                            df_y = df[df['Vuosi'] == year].copy()

                            df_y['Aika'] = pd.to_datetime(df_y['Aika'], errors='coerce')
                            df_y = df_y[~((df_y['Aika'].dt.month == 2) & (df_y['Aika'].dt.day == 29))]
                            df_y['date_md'] = pd.to_datetime(
                                df_y['Aika'].dt.strftime('%d.%m.') + '2000',
                                format='%d.%m.%Y'
                            )

                            idx_closest = (df_y['date_md'] - xdt).abs().idxmin()
                            q_val = float(df_y.loc[idx_closest, var_name0])
                            texts.append(f"{year}: {q_val:.2f}")

                        # --- Then add range Min / Max / Avg (ka) ---
                        try:
                            idx_range = (min_max_ka_df["Date"] - xdt).abs().idxmin()
                            vmin = float(min_max_ka_df.loc[idx_range, "Min"])
                            vmax = float(min_max_ka_df.loc[idx_range, "Max"])
                            vka  = float(min_max_ka_df.loc[idx_range, "keskiarvo"])

                            texts.append(f"min: {vmin:.2f}")
                            texts.append(f"max: {vmax:.2f}")
                            texts.append(f"ka: {vka:.2f}")
                        except Exception:
                            pass

                        # Combine all lines into one annotation
                        text = xdt.strftime('%d.%m.') + "<br>" + "<br>".join(texts)
                        clicked_lines.append({"x": x_iso, "text": text})

                except Exception:
                    pass

        # ---------- Draw all stored vertical lines + annotations ----------
        # iterate clicked_dates and add shape + annotation for each
        for item in clicked_lines:
            try:
                xdt = pd.to_datetime(item['x'])
                text = item['text']
            except Exception:
                continue
            fig.add_shape(
                type='line', x0=xdt, x1=xdt, y0=0, y1=1,
                xref='x', yref='paper',
                line=dict(color='orange', width=2, dash='dot')
            )
            fig.add_annotation(
                x=xdt, y=1.02, xref='x', yref='paper',
                showarrow=False,
                text=text,
                bgcolor='white',
                bordercolor='black',
                borderpad=4
            )
        return fig, clicked_lines
    
    @app.callback(
        Output('year-dropdown', 'value'),
        Input('year-dropdown', 'value'),
        Input('allow-2-years', 'value'),
    )
    ## Funktio joka rajoittaa vuosien valinnan 1 tai 2 vuoteen käyttäjän valinnan mukaan. 
    #  Jos "Salli 2 vuotta" on valittuna, käyttäjä voi valita enintään 2 vuotta. Muuten vain 1 vuosi on sallittu.
    def limit_year_selection(selected_years, allow2):
        if not selected_years:
            return []

        if not isinstance(selected_years, list):
            selected_years = [selected_years]

        allow_two = "yes" in (allow2 or [])

        # ---- Allow only 1 year ----
        if not allow_two:
            # keep the most recently selected year
            return [selected_years[-1]]

        # ---- Allow up to 2 years ----
        if len(selected_years) > 2:
            # keep first + last (your old logic)
            return [selected_years[0], selected_years[-1]]

        return selected_years

        
    ## Callback joka näyttää kuvaajan alla lisätiedot, jos säännöstelyrajoista on määritetty lisätietoja. Lisätiedot haetaan 'lisätieto-store' -storesta.
    @app.callback(
        Output('lisatieto-div', 'children'),
        Input('lisatieto-store', 'data')
    )
    def show_lisatieto(lisatieto):
        return lisatieto if lisatieto else ""
    
    ## Callback joka päivittää tilastotiedot kuvaajan viereen. 
    #  Näytetään tilastotiedot koko aikaväliltä (precomputed) ja valituilta vuosilta (lasketaan lennossa). 
    #  Käytetään kahta eri storea: 'stats-store' koko aikavälin tilastoille ja 'season-store' kausitilastoille. Näytetään vain tilastotiedot, jotka on saatavilla.
    @app.callback(
        Output('stats-panel', 'children'),
        Input('year-dropdown', 'value'),
        State('data-store', 'data'),
        State('variable-names', 'data'),
        State('stats-store', 'data'),
        State('season-store', 'data'),
        State('season-defs-store', 'data')
    )

    def update_stats_panel(selected_years, data, variable_name, stats_data, seasonal_stats, season_defs):
    
        if not stats_data:
            return "Tilastoja ei saatavilla."
        
        if not seasonal_stats:
            return "Tilastoja ei saatavilla."

        # --------------------
        # Koko aikavälin tilastot (laskettu erikseen, ei lennossa)
        # --------------------
        whole = stats_data[0]
        whole_season = seasonal_stats

        # --------------------
        # Vuosikohtaiset tilastot (lasketaan lennossa)
        # --------------------
        df = pd.DataFrame(data)
        vanhin_vuosi = df['Vuosi'].min()
        uusin_vuosi = df['Vuosi'].max()
        year_range_label = f"{vanhin_vuosi}-{uusin_vuosi}"

        year_stats_list = []
        for year in selected_years:
            df_y = df[df['Vuosi'] == year]
            stats = {
                "HW":  df_y[variable_name].max(),
                "MW":  df_y[variable_name].mean(),
                "NW":  df_y[variable_name].min(),
                "HW-NW": df_y[variable_name].max() - df_y[variable_name].min(),
                "Q99": df_y[variable_name].quantile(0.99),
                "Q95": df_y[variable_name].quantile(0.95),
                "Q05": df_y[variable_name].quantile(0.05),
                "n": int(df_y[variable_name].count())
            }
            year_stats_list.append(stats)
        order = ["HW", "MHW", "MW", "MNW", "NW","HW-NW","KVV", "Q99", "Q95", "Q05", "n"]

        def fmt(x, key=None):
            if x is None or pd.isna(x):
                return "–"
            if key == "n":
                return f"{int(x)}"
            return f"{x:.2f}"

        table_rows = []
        for k in order:
            row_cells = []
            
            # First cell: statistic name
            row_cells.append(
                html.Td(
                    k,
                    style={'fontWeight':'600', 'textAlign':'left', 'padding':'2px 2px'}
                )
            )

            
            # Second cell: whole range value
            row_cells.append(
                html.Td(
                    fmt(whole.get(k)),
                    style={'textAlign':'right', 'padding':'2px 2px'}
                )
            )


            
            # Next cells: one per selected year
            for stats in year_stats_list:
                val = stats.get(k)
                row_cells.append(
                    html.Td(
                        fmt(val, k),
                        style={'textAlign':'right', 'padding':'2px 2px', 
                            'color':'#999' if val is None else 'black'}
                    )
                )
            
            # Add row to table body
            table_rows.append(html.Tr(row_cells))

        # ---------- Jaettu taulukon tyyli, jota käytetään molemmille taulukoille ----------
        PAD_H = "3px"
        PAD_V = "1px"

        TABLE_STYLE = {
            "width": "100%",
            "borderCollapse": "collapse",
            "borderSpacing": "0",
            "tableLayout": "fixed",
            "fontSize": "18px",
            "fontFamily": "Arial, sans-serif",
            "lineHeight": "1.2",
        }

        TH_LEFT = {"textAlign": "left", "padding": f"{PAD_V} {PAD_H}", "fontWeight": "600"}
        TH_RIGHT = {"textAlign": "right", "padding": f"{PAD_V} {PAD_H}", "fontWeight": "600"}

        TD_LABEL = {"textAlign": "left", "padding": f"{PAD_V} {PAD_H}", "fontWeight": "600"}
        TD_VAL = {"textAlign": "right", "padding": f"{PAD_V} {PAD_H}"}

        # numeric columns = (range column + selected years)
        num_cols = len(selected_years) + 1

        # --- Column widths tuned for 1 vs 2 years ---
        if len(selected_years) == 1:
            # Make numeric columns compact so they don't look far apart
            label_w = "44%"
            range_w = "28%"
            year_w = "28%"
            numeric_widths = [range_w, year_w]
        else:
            # 2 years: balanced layout
            label_w = "28%"
            numeric_w = f"{(100 - float(label_w.strip('%'))) / num_cols:.0f}%"
            numeric_widths = [numeric_w] * num_cols

        COLGROUP = html.Colgroup(
            [html.Col(style={"width": label_w})] +
            [html.Col(style={"width": w}) for w in numeric_widths]
        )

        ## Taulukko jossa esitetään koko aikavälin tilastot ja valittujen vuosien tilastot. Käytetään samaa rakennetta kuin kausitilastoissa, jotta ulkoasu on yhtenäinen. 
        #  Taulukko on jaettu kolmeen osaan: colgroup määrittelee sarakkeiden leveydet, thead sisältää otsikkorivin ja tbody sisältää datarivit.
        table = html.Table(
            [
                COLGROUP,
                html.Thead(
                    html.Tr(
                        [html.Th("", style=TH_LEFT)] +
                        [html.Th(year_range_label, style=TH_RIGHT)] +
                        [html.Th(str(year), style=TH_RIGHT) for year in selected_years]
                    )
                ),
                html.Tbody(table_rows)
            ],
            style=TABLE_STYLE
        )



        # --- Taulukko, joka esittää vuodenaikojen sekä käyttäjän määrittelemän aikavälin minimit ja maksimit ---

        # Make sure df has a 'month' column
        df['month'] = pd.to_datetime(df['Aika']).dt.month

        seasons = {
            "Talven": [12, 1, 2],
            "Kevään": [3, 4, 5],
            "Kesän": [6, 7, 8],
            "Syksyn": [9, 10, 11]
        }

        # Lasketaan yksittäisten vuosien tilastot kausittain. Käytetään season_defs-listaa, joka sisältää kausien määritelmät (nimi, aloitus- ja lopetuspvm). 
        # Tämä mahdollistaa joustavan kausimäärittelyn, joka ei perustu vain kuukausiin.
        year_season_stats_list = []  # list of dicts per year
        for year in selected_years:
            df_year = df[df['Vuosi'] == year].copy()
            df_year['Aika'] = pd.to_datetime(df_year['Aika'], errors='coerce')
            year_stats = {}

            for season_dict in season_defs:  # <-- loop over your list of season definitions
                season_name = season_dict["name"]
                start_md = season_dict["start"]  # e.g., "12-01"
                end_md   = season_dict["end"]    # e.g., "02-28"

                # Convert to datetime with arbitrary year 2000
                start_dt = pd.to_datetime(f"2000-{start_md}", format="%Y-%m-%d")
                end_dt   = pd.to_datetime(f"2000-{end_md}", format="%Y-%m-%d")

                # Map df_year to "dummy year 2000" for season filtering
                df_year['date_md'] = pd.to_datetime(df_year['Aika'].dt.strftime("%m-%d") + "-2000", format="%m-%d-%Y")

                # Handle seasons that wrap over the year end (e.g., Talvi 12-01 to 02-28)
                if start_dt <= end_dt:
                    df_season = df_year[(df_year['date_md'] >= start_dt) & (df_year['date_md'] <= end_dt)]
                else:
                    # Wrap-around: take either before end_dt OR after start_dt
                    df_season = df_year[(df_year['date_md'] >= start_dt) | (df_year['date_md'] <= end_dt)]

                if not df_season.empty:
                    year_stats[f"{season_name}_Min"] = df_season[variable_name].min()
                    year_stats[f"{season_name}_Max"] = df_season[variable_name].max()
                else:
                    year_stats[f"{season_name}_Min"] = None
                    year_stats[f"{season_name}_Max"] = None

            year_season_stats_list.append(year_stats)

        print(year_season_stats_list)
        season_rows = []
        for season_dict in season_defs:
            season_name = season_dict["name"]
            whole_max = whole_season.get(f"{season_name}_Max", None)
            whole_min = whole_season.get(f"{season_name}_Min", None)

            # Max row
            row_max = [f"{season_name} Max", fmt(whole_max)]
            for year_stats in year_season_stats_list:
                row_max.append(fmt(year_stats.get(f"{season_name}_Max")))
            season_rows.append(row_max)

            # Min row
            row_min = [f"{season_name} Min", fmt(whole_min)]
            for year_stats in year_season_stats_list:
                row_min.append(fmt(year_stats.get(f"{season_name}_Min")))
            season_rows.append(row_min)

        ## Taulukko, joka esittää kausittaiset minimit ja maksimit koko aikaväliltä ja valituilta vuosilta. 
        #  Käytetään samaa rakennetta kuin koko aikavälin tilastotaulukossa, jotta ulkoasu on yhtenäinen.
        seasonal_table = html.Table(
            [
                COLGROUP,
                html.Thead(
                    html.Tr(
                        [html.Th("", style=TH_LEFT)] +
                        [html.Th(year_range_label, style=TH_RIGHT)] +
                        [html.Th(str(year), style=TH_RIGHT) for year in selected_years]
                    )
                ),
                html.Tbody([
                    html.Tr(
                        [html.Td(row[0], style=TD_LABEL)] +
                        [html.Td(val, style=TD_VAL) for val in row[1:]]
                    )
                    for row in season_rows
                ])
            ],
            style={**TABLE_STYLE, "marginTop": "10px"}
        )


        return [
            html.H4(f"Tunnusluvut ({variable_name})", style={'marginBottom': '10px', 'fontSize': '24px'}),
            table, seasonal_table
        ]
    
    return app
