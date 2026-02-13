import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State

import pandas as pd

import plotly.graph_objects as go
from plotly.subplots import make_subplots

def init_dash(dataframe, variable_name, min_max_ka, rajat_df = None):

    app = dash.Dash(__name__)

    app.layout = html.Div([
        html.H2("Vuosittainen hydrologinen data"),    
        dcc.Store(id='data-store', data = dataframe.to_dict('records')),
        dcc.Store(id='clicked-lines', data=[]),
        dcc.Store(id='variable-names', data=variable_name),
        dcc.Store(id="min-max-ka", data = min_max_ka.to_dict('records')),
        dcc.Store(id="rajat", data = rajat_df.to_dict('records') if rajat_df is not None else None),


        # Dropdown-valikko vuosille
        dcc.Dropdown(
            id='year-dropdown',
            options=[{'label': y, 'value': y} for y in dataframe['Vuosi'].unique()],
            value=dataframe['Vuosi'].unique()[0]  # oletusvuosi
        ),

        html.Div([
            html.Button("Clear lines", id='clear-lines', n_clicks=0)
        ], style={'marginTop': '8px'}),
        
        # Kuvaaja
        dcc.Graph(id='hydro-graph')
    ])

    # Callback, joka päivittää kuvaajan
    @app.callback(
        Output('hydro-graph', 'figure'),
        Output('clicked-lines', 'data'),
        Input('year-dropdown', 'value'),
        Input('hydro-graph', 'clickData'),
        Input('clear-lines', 'n_clicks'),
        State('clicked-lines', 'data'),
        State('data-store', 'data'),
        State('variable-names','data'),
        State('min-max-ka', 'data'),
        State('rajat', 'data')
    )

    
    def update_graph(selected_year,clickData, clear_nclicks, clicked_lines, data, variable_name, min_max_ka, rajat):
        # Suodata valittu vuosi
        df = pd.DataFrame(data)
        min_max_ka_df = pd.DataFrame(min_max_ka)
        df_year = df.loc[df['Vuosi'] == selected_year].copy()
        df_year[variable_name] = df_year[variable_name].astype(float)
        df_year.loc[:, variable_name] *= 1.0
        df_year['Aika'] = pd.to_datetime(df_year['Aika'])
        df_year['date_md'] = pd.to_datetime(df_year['Aika'].dt.strftime('%d.%m.') + '2000', format='%d.%m.%Y')
        # Luo kuvaaja, jossa kaikki kolme muuttujaa
        print("Rajat:")
        print(rajat)
        
        # Create subplot with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
                            
        
        # lisää min max ja keskiarvo

        fig.add_trace(
            go.Scatter(x=min_max_ka_df['Date'], y=min_max_ka_df['Min'].interpolate(),
                    name='Minimi',mode='lines', line=dict(width=3, color='blue', dash = 'dash')),
            secondary_y=False
        )

        fig.add_trace(
            go.Scatter(x=min_max_ka_df['Date'], y=min_max_ka_df['Max'].interpolate(),
                    name='Maksimi',mode='lines', line=dict(width=3, color='red', dash = 'dash')),
            secondary_y=False
        )

        fig.add_trace(
            go.Scatter(x=min_max_ka_df['Date'], y=min_max_ka_df['keskiarvo'].interpolate(),
                    name='Keskiarvo',mode='lines', line=dict(width=3,  color='grey', dash = 'dash')),
            secondary_y=False
        )

                # Add first trace (0406460_Q) on secondary y-axis
        var_name0 = variable_name
        fig.add_trace(
            go.Scatter(x=df_year['date_md'], y=df_year[var_name0],
                    name=var_name0, line=dict(color='orange')),secondary_y=False)
        
        if rajat is not None:
            df_rajat = pd.DataFrame(rajat)
            fig.add_trace(
            go.Scatter(x=df_rajat['date_md'], y=df_rajat['alaraja'].interpolate(),
                    name="Alaraja", line=dict(color='black')),secondary_y=False)
            
            fig.add_trace(
            go.Scatter(x=df_rajat['date_md'], y=df_rajat['yläraja'].interpolate(),
                    name="Yläraja", line=dict(color='black')),secondary_y=False)
        
        
        fig.update_layout(
        title_text="Hydrologinen data",
        height = 800,
        hovermode='x unified',             # unified hover across traces -> vertical "tracking" box
        )
        fig.update_xaxes(
            title_text="Aika",
            showspikes=True,                   # enable spike (vertical line)
            spikemode='across',
            spikesnap='cursor',
            spikecolor='gray',
            spikethickness=1
        )

        # Update axis titles
        fig.update_layout(title_text="Hydrologinen data")
        fig.update_xaxes(title_text="Aika")
        fig.update_yaxes(title_text=var_name0, secondary_y=False)

# ---------- Manage the clicked_dates store ----------
        # Handle clear button
        ctx = dash.callback_context
        trigger = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

        if trigger == 'clear-lines':
            clicked_lines = []

        elif trigger == 'year-dropdown':
            clicked_lines = []

        elif trigger == 'hydro-graph' and clickData and 'points' in clickData:
            x_clicked = clickData['points'][0].get('x')
            if x_clicked is not None:
                try:
                    xdt = pd.to_datetime(x_clicked)
                    x_iso = xdt.isoformat()

                    if not any(d['x'] == x_iso for d in clicked_lines):
                        idx_closest = (df_year['date_md'] - xdt).abs().idxmin()
                        q_val = float(df_year.loc[idx_closest, var_name0])
                        text = f"{xdt.strftime('%d.%m')}<br>W: {q_val:.2f}"
                        clicked_lines.append({"x": x_iso, "text": text})
                except Exception:
                    pass

        # Handle click to add new vertical line + annotation
        elif clickData and 'points' in clickData and len(clickData['points']) > 0:
            x_clicked = clickData['points'][0].get('x')
            if x_clicked is not None:
                try:
                    xdt = pd.to_datetime(x_clicked)
                    x_iso = xdt.isoformat()
                    # Append new line with annotation text
                    if not any(d['x'] == x_iso for d in clicked_lines):  # prevent duplicates
                        print("Appending")
                        # Find closest row in df_year
                        idx_closest = (df_year['date_md'] - xdt).abs().idxmin()
                        print(idx_closest)
                        # Capture hover values from your traces
                        q_val = float(df_year.loc[idx_closest, var_name0])
                        print(q_val)


                        # Combine date + hover values
                        text = f"{xdt.strftime('%d.%m')}<br>W: {q_val:.2f}"
                        # Append new vertical line + annotation
                        clicked_lines.append({"x": x_iso, "text": text})
                        print(clicked_lines)
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
    
    return app
