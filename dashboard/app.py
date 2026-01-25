import dash
from dash import dcc, html, Input, Output
import plotly.express as px
import duckdb
import pandas as pd


app = dash.Dash(__name__)


app.layout = html.Div([
      html.H1("Real-time Environmental Air Quality Monitoring Dashboard", style={"textAlign": "center"}),
      dcc.Tabs([
            dcc.Tab(
                  label="Sensor Locations",
                  children=[dcc.Graph(id="map-view")]
            ),
            dcc.Tab(
                  label="Parameter Plots",
                  children=[
                        html.Div([
                              html.Label("Select Parameter:", style={"fontWeight": "bold", "marginRight": "10px"}),
                              dcc.Dropdown(
                                    id="parameter-dropdown",
                                    clearable=False,
                                    multi=False,
                                    searchable=True,
                                    style={"width": "300px"}
                              ),
                        ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px", "marginTop": "20px"}),
                        html.Div([
                              html.Label("Select Date Range:", style={"fontWeight": "bold", "marginRight": "10px"}),
                              dcc.DatePickerRange(
                                    id="date-picker-range",
                                    display_format="YYYY-MM-DD"
                              ),
                        ], style={"display": "flex", "alignItems": "center", "marginBottom": "20px"}),
                        dcc.Graph(id="line-plot", style={"height": "500px"}),
                        dcc.Graph(id="bar-plot", style={"height": "500px"})
                  ]
            )
      ])
], style={"padding": "20px"})

@app.callback(
      Output("map-view", "figure"),
      Input("map-view", "id")
)
def update_map(_):

      with duckdb.connect("../air_quality.db", read_only=True) as db_connection:
        latest_values_df = db_connection.execute(
            "SELECT * FROM presentation.latest_param_values_per_location"
        ).fetchdf()

      latest_values_df.fillna(0, inplace=True)

      # Calculate center of all locations
      center_lat = latest_values_df["lat"].mean()
      center_lon = latest_values_df["lon"].mean()

      map_fig = px.scatter_mapbox(
            latest_values_df,
            lat="lat",
            lon="lon",
            hover_name="location",
            hover_data={
                "lat": False,
                "lon": False,
                "datetime":True,
                "pm10": True,
                "pm25": True,
                "so2": True
            },
            zoom=5.5,
            size_max=25,
            center={"lat": center_lat, "lon": center_lon}
      )

      map_fig.update_traces(
            marker=dict(size=20, opacity=0.9, color="red")
      )

      map_fig.update_layout(
            mapbox_style="open-street-map",
            height=800,
            title="Air Quality Monitoring Locations",
            margin={"r": 0, "t": 40, "l": 0, "b": 0}
      )

      return map_fig


@app.callback(
    [
        Output("parameter-dropdown", "options"),
        Output("parameter-dropdown", "value"),
        Output("date-picker-range", "start_date"),
        Output("date-picker-range", "end_date"),
    ],
    Input("parameter-dropdown", "id"),
)
def update_dropdowns(_):
    with duckdb.connect("../air_quality.db", read_only=True) as db_connection:
        df = db_connection.execute(
            "SELECT * FROM presentation.daily_air_quality_stats"
        ).fetchdf()

    parameter_options = [
        {"label": parameter, "value": parameter}
        for parameter in df["parameter"].unique()
    ]
    start_date = df["measurement_date"].min()
    end_date = df["measurement_date"].max()

    return (
        parameter_options,
        df["parameter"].unique()[0],
        start_date,
        end_date,
    )


@app.callback(
      [Output("line-plot", "figure"), Output("bar-plot", "figure")],
      [
            Input("parameter-dropdown", "value"),
            Input("date-picker-range", "start_date"),
            Input("date-picker-range", "end_date")
      ]
)
def update_plots(selected_parameter, start_date, end_date):

      with duckdb.connect("../air_quality.db", read_only=True) as db_connection:
        daily_stats_df = db_connection.execute(
            "SELECT * FROM presentation.daily_air_quality_stats"
        ).fetchdf()

      # Filter by parameter and date only (show all locations)
      filtered_df = daily_stats_df[daily_stats_df["parameter"] == selected_parameter]
      filtered_df = filtered_df[
            (filtered_df["measurement_date"] >= pd.to_datetime(start_date))
            & (filtered_df["measurement_date"] <= pd.to_datetime(end_date))
      ]

      # Get the unit for labels
      unit = filtered_df["units"].unique()[0] if len(filtered_df["units"].unique()) > 0 else "Value"

      labels = {
        "average_value": unit,
        "measurement_date": "Date",
        "location": "Location"
      }

      # Line plot with all locations (different colors for each location)
      line_fig = px.line(
            filtered_df.sort_values(by=["location", "measurement_date"]),
            x="measurement_date",
            y="average_value",
            color="location",
            labels=labels,
            title=f"Plot Over Time of {selected_parameter} Levels for All Locations"
      )

      line_fig.update_layout(
            xaxis_title="Date",
            yaxis_title=unit,
            legend_title="Location",
            hovermode="x unified"
      )

      # Bar chart showing average values by location
      avg_by_location = filtered_df.groupby("location")["average_value"].mean().reset_index()
      avg_by_location = avg_by_location.sort_values(by="average_value", ascending=False)

      bar_fig = px.bar(
            avg_by_location,
            x="location",
            y="average_value",
            labels={"average_value": unit, "location": "Location"},
            title=f"Average {selected_parameter} Levels by Location",
            color="location"
      )

      bar_fig.update_layout(
            xaxis_title="Location",
            yaxis_title=f"Average {unit}",
            showlegend=False,
            xaxis={'categoryorder': 'total descending'}
      )

      return line_fig, bar_fig


if __name__ == "__main__":
    app.run_server(debug=True)