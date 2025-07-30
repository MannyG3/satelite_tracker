# pip install dash plotly
from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go
import numpy as np
import random

# Constants
NUM_LEO = 50
NUM_GEO = 50
EARTH_RADIUS = 6371  # km
LEO_ALTITUDE = 2000
GEO_ALTITUDE = 35786
INITIAL_THRESHOLD = 100  # km

# Generate satellites with stored angles for animation
def generate_satellites(num, altitude, label_prefix):
    sats = []
    for i in range(num):
        theta = np.radians(random.uniform(0, 180))
        phi   = np.radians(random.uniform(0, 360))
        r     = EARTH_RADIUS + altitude
        x = r * np.sin(theta) * np.cos(phi)
        y = r * np.sin(theta) * np.sin(phi)
        z = r * np.cos(theta)
        sats.append({
            'id': f"{label_prefix}_{i+1}",
            'type': label_prefix,
            'theta': theta,
            'phi':   phi,
            'r':     r,
            'x':     x,
            'y':     y,
            'z':     z
        })
    return sats

leo_sats = generate_satellites(NUM_LEO, LEO_ALTITUDE, 'LEO')
geo_sats = generate_satellites(NUM_GEO, GEO_ALTITUDE, 'GEO')
all_sats = leo_sats + geo_sats

# Update positions by incrementing phi
def update_positions(sats, dphi):
    for s in sats:
        s['phi'] = (s['phi'] + dphi) % (2 * np.pi)
        th, ph, r = s['theta'], s['phi'], s['r']
        s['x'] = r * np.sin(th) * np.cos(ph)
        s['y'] = r * np.sin(th) * np.sin(ph)
        s['z'] = r * np.cos(th)

# Collision detection
def detect_collisions(sats, threshold):
    links = []
    for i in range(len(sats)):
        for j in range(i+1, len(sats)):
            a, b = sats[i], sats[j]
            dist = np.linalg.norm((a['x']-b['x'], a['y']-b['y'], a['z']-b['z']))
            if dist < threshold:
                links.append((i, j))
    return links

# Earth surface mesh
u, v = np.mgrid[0:2*np.pi:50j, 0:np.pi:25j]
xe = EARTH_RADIUS * np.cos(u) * np.sin(v)
ye = EARTH_RADIUS * np.sin(u) * np.sin(v)
ze = EARTH_RADIUS * np.cos(v)
earth_surface = go.Surface(
    x=xe, y=ye, z=ze,
    colorscale=[[0, 'darkblue'], [1, 'green']],
    opacity=0.8, showscale=False, name='Earth'
)

# Build initial figure (for layout defaults)
def make_figure(threshold, clickData, preset):
    # Animate orbits a bit each update
    update_positions(all_sats, np.radians(0.5))

    # Separate LEO/GEO lists
    leo = [s for s in all_sats if s['type']=='LEO']
    geo = [s for s in all_sats if s['type']=='GEO']

    # Satellite scatter traces with hovertemplate
    leo_trace = go.Scatter3d(
        x=[s['x'] for s in leo],
        y=[s['y'] for s in leo],
        z=[s['z'] for s in leo],
        mode='markers',
        marker=dict(size=4, color='yellow'),
        name='LEO Satellites',
        customdata=[s['id'] for s in leo],
        hovertemplate="<b>%{customdata}</b><br>x: %{x:.0f} km<br>y: %{y:.0f} km<br>z: %{z:.0f} km<extra></extra>"
    )
    geo_trace = go.Scatter3d(
        x=[s['x'] for s in geo],
        y=[s['y'] for s in geo],
        z=[s['z'] for s in geo],
        mode='markers',
        marker=dict(size=4, color='red'),
        name='GEO Satellites',
        customdata=[s['id'] for s in geo],
        hovertemplate="<b>%{customdata}</b><br>x: %{x:.0f} km<br>y: %{y:.0f} km<br>z: %{z:.0f} km<extra></extra>"
    )

    # Collision links
    links = detect_collisions(all_sats, threshold)
    collision_traces = []
    for i, j in links:
        a, b = all_sats[i], all_sats[j]
        collision_traces.append(
            go.Scatter3d(
                x=[a['x'], b['x']],
                y=[a['y'], b['y']],
                z=[a['z'], b['z']],
                mode='lines',
                line=dict(color='cyan', width=2),
                showlegend=False
            )
        )

    # Assemble figure
    fig = go.Figure(data=[earth_surface, leo_trace, geo_trace] + collision_traces)
    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            bgcolor='black',
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=40),
        showlegend=True
    )

    # Handle click zoom
    info = "Click on a satellite to zoom and view details."
    if clickData and clickData.get('points'):
        pid = clickData['points'][0]['customdata']
        sat = next((s for s in all_sats if s['id']==pid), None)
        if sat:
            # highlight
            fig.add_trace(go.Scatter3d(
                x=[sat['x']], y=[sat['y']], z=[sat['z']],
                mode='markers',
                marker=dict(size=10, color='cyan'),
                name='Selected Satellite'
            ))
            # camera on sat
            cam = dict(eye=dict(
                x=sat['x']/sat['r']*3,
                y=sat['y']/sat['r']*3,
                z=sat['z']/sat['r']*3
            ))
            fig.update_layout(scene_camera=cam)
            info = (f"🛰 <b>{sat['id']}</b> | Type: {sat['type']} | "
                    f"Altitude: {sat['r']-EARTH_RADIUS:.1f} km")
    # Apply camera preset if no click
    elif preset != 'default':
        R = EARTH_RADIUS + GEO_ALTITUDE
        cams = {
            'top':         dict(eye=dict(x=0, y=0, z=3*R)),
            'equatorial':  dict(eye=dict(x=3*R, y=0, z=0)),
            'side':        dict(eye=dict(x=0, y=3*R, z=0))
        }
        if preset in cams:
            fig.update_layout(scene_camera=cams[preset])

    return fig, info

# Dash app
app = Dash(__name__)
server = app.server

app.layout = html.Div([
    html.H1("Space Traffic Management System",
            style={'textAlign':'center','color':'white'}),
    dcc.Slider(
        id='threshold-slider',
        min=10, max=500, step=10, value=INITIAL_THRESHOLD,
        marks={i: f"{i} km" for i in range(0,501,100)},
        tooltip={'always_visible':True, 'placement':'bottom'}
    ),
    html.Div([
        html.Label('Camera view:', style={'color':'white'}),
        dcc.RadioItems(
            id='camera-presets',
            options=[
                {'label':'Default','value':'default'},
                {'label':'Top‑down','value':'top'},
                {'label':'Equatorial','value':'equatorial'},
                {'label':'Side','value':'side'},
            ],
            value='default',
            labelStyle={'display':'inline-block','margin':'0 10px','color':'white'}
        )
    ], style={'textAlign':'center','padding':'10px'}),
    dcc.Graph(id='3d-sim',
              figure=make_figure(INITIAL_THRESHOLD, None, 'default'),
              style={'height':'80vh'}),
    html.Div("Click on a satellite to zoom and view details.",
             id='satellite-info',
             style={'color':'white','padding':'10px','textAlign':'center'}),
    dcc.Interval(id='interval-component', interval=500, n_intervals=0)
], style={'backgroundColor':'black'})

@app.callback(
    Output('3d-sim', 'figure'),
    Output('satellite-info', 'children'),
    Input('interval-component', 'n_intervals'),
    Input('3d-sim', 'clickData'),
    Input('threshold-slider', 'value'),
    Input('camera-presets', 'value'),
)
def update_graph(n_intervals, clickData, threshold, preset):
    return make_figure(threshold, clickData, preset)

if __name__ == "__main__":
    app.run(debug=False)
