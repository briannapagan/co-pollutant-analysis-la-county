import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from folium.plugins import MarkerCluster, HeatMap
from folium.plugins import Geocoder
from folium.plugins import MousePosition
import plotly.express as px
import copy

@st.cache(allow_output_mutation=True)
def load_data():
    file_path = 'data/2020_NEI_LACounty_Facilities.xlsx'
    data = pd.read_excel(file_path)
    data['Emissions (Tons)'] = data['Emissions (Tons)'].round(3)
    gdfs = []
    grouped_data = data.groupby('Pollutant')
    for pollutant, group in grouped_data:
        geometry = [Point(xy) for xy in zip(group['Longitude'], group['Latitude'])]
        gdf = gpd.GeoDataFrame(group, geometry=geometry)
        gdfs.append((pollutant, gdf))
    return gdfs

gdfs = load_data()

def get_data_for_pollutant(selected_pollutant):
    # Use deepcopy to avoid mutating cached data
    for pollutant, gdf in copy.deepcopy(gdfs):
        if pollutant == selected_pollutant:
            return gdf
    return None

pollutants = [pollutant for pollutant, gdf in gdfs]
selected_pollutant = st.selectbox('Select Pollutant', pollutants)

def create_pie_chart(selected_gdf):
    emissions_by_facility = selected_gdf.groupby('Facility Type')['Emissions (Tons)'].sum().reset_index()
    total_emissions = emissions_by_facility['Emissions (Tons)'].sum()
    significant_facilities = emissions_by_facility[emissions_by_facility['Emissions (Tons)'] >= 0.1 * total_emissions]
    other_emissions = total_emissions - significant_facilities['Emissions (Tons)'].sum()
    other_row = {'Facility Type': 'Other', 'Emissions (Tons)': other_emissions}
    combined_data = pd.concat([significant_facilities, pd.DataFrame([other_row])])
    fig = px.pie(combined_data, values='Emissions (Tons)', names='Facility Type', 
                 title=f'Total Emissions of {selected_pollutant} by Facility Type (Grouping < 10% into "Other")')
    return fig

def render_folium_map(m):
    """ Function to display folium map in Streamlit """
    from streamlit_folium import folium_static
    folium_static(m)

def update_map(selected_pollutant):
    # Clear existing map
    m = folium.Map(location=[34.052235, -118.243683], zoom_start=9, prefer_canvas=True, control_scale=True)
    folium.TileLayer('cartodbpositron',show= True).add_to(m)



    
    # Add LA County boundary polygon
    la_county_boundary = gpd.read_file('data/County_Boundary.geojson')
    la_county_boundary = la_county_boundary.to_crs(epsg=4326)  # Set CRS to EPSG:4326 (WGS84)
    folium.GeoJson(la_county_boundary, name='LA County Boundary').add_to(m)
    
    # Get GeoDataFrame for selected pollutant
    selected_gdf = next((gdf for pollutant_name, gdf in gdfs if pollutant_name == selected_pollutant), None)
    
    if selected_gdf is not None:
        # Group facilities by their coordinates and sum emissions
        grouped_data = selected_gdf.groupby(['Latitude', 'Longitude'])['Emissions (Tons)'].sum().round(2)
        
        # Create HeatMap layer
        heat_data = [[lat, lon, emissions] for (lat, lon), emissions in grouped_data.items()]
        HeatMap(heat_data, name='Heat Map').add_to(m)
        
        # Create MarkerCluster with custom icon create function
        icon_create_function = '''
            function(cluster) {
                var sum = 0;
                cluster.getAllChildMarkers().forEach(function(marker) {
                    sum += marker.options.props.emissions;
                });
                return L.divIcon({
                    html: '<div style="font-size: 16px;"><b>' + sum + '</b></div>',
                    className: 'marker-cluster marker-cluster-small',
                    iconSize: new L.Point(20, 20)
                });
            }
        '''
        marker_cluster = MarkerCluster(icon_create_function=icon_create_function, name='Labels').add_to(m)
        
        # Add markers to MarkerCluster
        for idx, row in selected_gdf.iterrows():
            popup_text = f"<div style='width: 300px;'> \
                          <b>Facility:</b> {row['SITE  NAME']}<br> \
                          <b>State-County:</b> {row['State-County']}<br> \
                          <b>EPA Region:</b> {row['EPA Region']}<br> \
                          <b>Pollutant Type:</b> {row['Pollutant Type']}<br> \
                          <b>Emissions:</b> {row['Emissions (Tons)']} Tons</div>"
            marker = folium.Marker([row['Latitude'], row['Longitude']], popup=popup_text, tooltip=popup_text)
            marker_cluster.add_child(marker)
            marker.options['props'] = {'emissions': row['Emissions (Tons)']}  # Add emissions property to marker
            
        # Create pie chart
        #fig = create_pie_chart(selected_pollutant)
       
    
    # Add search bar
    Geocoder().add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Add coordinates on mouse position
    MousePosition().add_to(m)
    
    # Display map
    render_folium_map(m)
    fig = create_pie_chart(selected_gdf)
    st.plotly_chart(fig)

update_map(selected_pollutant)
