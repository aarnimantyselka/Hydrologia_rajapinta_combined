import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def init_combined_dash(vk_df, virtaama_df, vk_min_max=None, vk_name="Vedenkorkeus", virtaama_name="Virtaama"):
    """
    vk_df: vedenkorkeus dataframe, must have 'Date' and 'Arvo' columns
    virtaama_df: virtaama dataframe, must have 'Date' and 'Arvo' columns
    vk_min_max: optional dataframe with 'Date', 'Min', 'Max', 'keskiarvo' for vedenkorkeus
    """

    app = dash.Dash(__name__)

    app.layout = html.Div([
        html.H2("Vedenkorkeus ja Virtaama"),
        dcc.Store(id='vk-store', data=vk_df.to_dict('records')),
        dcc.Store(id='virtaama-store', data=virtaama_df.to_dict('records')),
        dcc.Store(id='min-max-store', data=vk_min_max.to_dict('records') if vk_min_max is not None else None),

        # Dropdown to select years
        dcc.Dropdown(
            id='year-dropdown',
            options=[{'label': y, 'value': y} for y in vk_df['Date'].dt.year.unique()],
            value=[vk_df['Date'].dt.year.unique()[0]],
            multi=True
        ),

        # The graph
        dcc.Graph(id='combined-graph')
    ])

    @app.callback(
        Output('combined-graph', 'figure'),
        Input('year-dropdown', 'value'),
        State('vk-store', 'data'),
        State('virtaama-store', 'data'),
        State('min-max-store', 'data')
    )
    def update_graph(selected_years, vk_data, virtaama_data, min_max_data):
        vk = pd.DataFrame(vk_data)
        virtaama = pd.DataFrame(virtaama_data)
        min_max = pd.DataFrame(min_max_data) if min_max_data is not None else None

        vk['Date'] = pd.to_datetime(vk['Date'])
        virtaama['Date'] = pd.to_datetime(virtaama['Date'])
        vk['Year'] = vk['Date'].dt.year
        virtaama['Year'] = virtaama['Date'].dt.year

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # --- Plot min/max/average as background
        if min_max is not None:
            min_max['Date'] = pd.to_datetime(min_max['Date'])
            fig.add_trace(go.Scatter(
                x=min_max['Date'], y=min_max['Min'], line=dict(width=0.8, color='lightblue'),
                name="Min", showlegend=True
            ), secondary_y=False)
            fig.add_trace(go.Scatter(
                x=min_max['Date'], y=min_max['Max'], line=dict(width=0.8, color='lightblue'),
                fill='tonexty', fillcolor='rgba(173,216,230,0.3)', name="Max", showlegend=True
            ), secondary_y=False)
            fig.add_trace(go.Scatter(
                x=min_max['Date'], y=min_max['keskiarvo'], line=dict(width=1.5, color='blue', dash='dash'),
                name="Keskiarvo"
            ), secondary_y=False)

        # --- Plot per-year vedenkorkeus
        colors_vk = ['orange', 'green', 'purple', 'brown']
        for i, year in enumerate(selected_years):
            vk_y = vk[vk['Year'] == year].copy()
            vk_y = vk_y[~((vk_y['Date'].dt.month==2) & (vk_y['Date'].dt.day==29))]  # skip leap day
            vk_y['date_md'] = pd.to_datetime(vk_y['Date'].dt.strftime('%d.%m.') + '2000', format='%d.%m.%Y')
            fig.add_trace(go.Scatter(
                x=vk_y['date_md'], y=vk_y['Arvo'], name=f"{year} {vk_name}",
                line=dict(color=colors_vk[i % len(colors_vk)])
            ), secondary_y=False)

        # --- Plot per-year virtaama
        colors_v = ['red', 'magenta', 'darkred', 'crimson']
        for i, year in enumerate(selected_years):
            v_y = virtaama[virtaama['Year'] == year].copy()
            v_y = v_y[~((v_y['Date'].dt.month==2) & (v_y['Date'].dt.day==29))]
            v_y['date_md'] = pd.to_datetime(v_y['Date'].dt.strftime('%d.%m.') + '2000', format='%d.%m.%Y')
            fig.add_trace(go.Scatter(
                x=v_y['date_md'], y=v_y['Arvo'], name=f"{year} {virtaama_name}",
                line=dict(color=colors_v[i % len(colors_v)])
            ), secondary_y=True)

        fig.update_layout(
            title="Vedenkorkeus ja Virtaama",
            xaxis_title="Päivämäärä",
            yaxis_title=f"{vk_name} (m)",
            yaxis2_title=f"{virtaama_name} (m³/s)",
            height=700, width=1200,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        return fig


    return app
