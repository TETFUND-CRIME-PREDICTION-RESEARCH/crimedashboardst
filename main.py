from datetime import datetime
import requests
import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import os
import json
from geopy.geocoders import Bing
from dotenv import load_dotenv

load_dotenv()

bing_map_api = os.getenv('BING_MAP_API')
BASE_URL = os.getenv('BASE_URL')
NIGERIA_COORDINATES = [8.758432712612587, 15.367627426766712]

def check_server_status():
    try:
        response = requests.get(BASE_URL + "status")
        response.raise_for_status()
        return response.json()["status code"]
    except requests.exceptions.RequestException as e:
        print("Error fetching server status: {}".format(e))
        return None

@st.cache_data
def fetch_crime_data(state_filter, year):
    params = {"state": state_filter}
    if year != "All":
        params["year"] = year
    response = requests.get(BASE_URL + "crime_events", params=params)
    response.raise_for_status()
    return response.json()["data"]

def crime_overview():
    try:
        states = requests.get(BASE_URL + "states")
        states.raise_for_status()
        if states.status_code != 200:
            st.error("Error fetching states data: {}".format(states.text))
            return
        try:
            st.session_state.states = ["All"] +  states.json()['states']
        except KeyError:
            st.error("Error fetching states data: {}".format(states.text))
            return
    except requests.exceptions.RequestException as e:
        st.error("Error fetching states data: {}".format(e))
        return

    if 'state_filter' not in st.session_state:
        st.session_state.state_filter = "All"
    if 'actors_filter' not in st.session_state:
        st.session_state.actors_filter = "All"
    if 'event_types_filter' not in st.session_state:
        st.session_state.event_types_filter = "All"

    state_filter = st.sidebar.selectbox("Select State", st.session_state.states)

    try:
        actors = ["All"] + requests.get(BASE_URL + "actors").json()['actors']
        st.session_state.actors = actors
    except requests.exceptions.RequestException as e:
        st.error("Error fetching actors data: {}".format(e))
        return
    actor_filter = st.sidebar.selectbox("Select Actor", actors)

    try:
        event_types = ["All"] + requests.get(BASE_URL + "event_types").json()['event_types']
        st.session_state.event_types = event_types
    except requests.exceptions.RequestException as e:
        st.error("Error fetching event types data: {}".format(e))
        return
    event_type_filter = st.sidebar.selectbox("Select Event Type", event_types)

    st.session_state.state_filter = state_filter
    st.session_state.actors_filter = actor_filter
    st.session_state.event_types_filter = event_type_filter

    if state_filter == "All":
        state_filter = None
    if actor_filter == "All":
        actor_filter = None
    if event_type_filter == "All":
        event_type_filter = None

    try:
        historical_events = requests.get(BASE_URL + "overview/historical", params={"location": state_filter, "actor1": actor_filter, "event_type": event_type_filter}).json()["data"]
        if not historical_events:
            st.warning("No historical events data available for the selected filters.")
            st.session_state.historical_events = pd.DataFrame()  # Initialize as an empty DataFrame
            return
    except requests.exceptions.RequestException as e:
        st.error("Error fetching historical events data: {}".format(e))
        return

    data = pd.read_json(json.dumps(historical_events))
    num_incidences = data.total_crimes.sum()
    st.session_state.historical_events = data

    col1, col2, col4 = st.columns([1, 1, 2])
    col3 = st.columns([1])[0]

    col1.metric("Total Incidences", num_incidences)

    try:
        if state_filter:
            rank = requests.get(BASE_URL + "overview/rank", params={"state": state_filter, "actor1": actor_filter, "event_type": event_type_filter}).json()["data"]["rank"]
            col2.metric("State Rank", rank)
        else:
            most_affected_state = requests.get(BASE_URL + "overview/most_affected_state", params={"actor1": actor_filter, "event_type": event_type_filter}).json()["data"]['state']
            col2.metric("Most Affected State", most_affected_state)
    except requests.exceptions.RequestException as e:
        st.error("Error fetching ranking data: {}".format(e))
        return

    try:
        most_active_actor = requests.get(BASE_URL + "overview/most_active_actor", params={"location": state_filter, "event_type": event_type_filter}).json()["data"]['actor1']
        col3.metric("Most Active Actor", most_active_actor)
    except requests.exceptions.RequestException as e:
        st.error("Error fetching most active actor data: {}".format(e))
        return

    try:
        most_affected_lga = requests.get(BASE_URL + "overview/most_affected_lga", params={"state": state_filter, "actor1": actor_filter, "event_type": event_type_filter}).json()['data']['lga']
        col4.metric("Most Affected LGA", most_affected_lga)
    except requests.exceptions.RequestException as e:
        st.error("Error fetching most affected LGA data: {}".format(e))
        return

def plot_historical_bar():
    if 'historical_events' in st.session_state and not st.session_state.historical_events.empty:
        data = st.session_state.historical_events
        if st.session_state.state_filter == "All":
            st.subheader("Cumulative Crime Incidences for All States")
        else:
            st.subheader("Cumulative Crime Incidences for :blue[{}] State".format(st.session_state.state_filter))
        st.bar_chart(data.set_index("year")["total_crimes"], use_container_width=True)
    else:
        st.warning("No data available to display.")

def section_break():
    st.markdown("---")

def plot_historical_line():
    if 'historical_events' in st.session_state and not st.session_state.historical_events.empty:
        data = st.session_state.historical_events
        st.line_chart(data.set_index("year")["total_crimes"], use_container_width=True)
    else:
        st.warning("No data available to display.")

def display_country_map():
    try:
        state_filter = st.session_state.state_filter if st.session_state.state_filter != "All" else None
        st.subheader("Crime Incidences Map")

        year_options = list(range(datetime.now().year, 2009, -1))
        year = st.selectbox("Select Year", year_options)
        # set default year to the current year
        if not year:
            year = datetime.now().year

        crime_events = fetch_crime_data(state_filter, year)
        crime_data = pd.read_json(json.dumps(crime_events))

        st.write("Number of crime events: ", crime_data.shape[0])

        if state_filter is None:
            nigeria_map = folium.Map(location=NIGERIA_COORDINATES, zoom_start=6)
        else:
            geolocator = Bing(api_key=bing_map_api)
            location = geolocator.geocode(state_filter + ", Nigeria")
            nigeria_map = folium.Map(location=[location.latitude, location.longitude], zoom_start=9)

        folium.TileLayer('cartodbpositron').add_to(nigeria_map)
        marker_cluster = MarkerCluster().add_to(nigeria_map)

        st.warning("The red circle size represents the number of fatalities in the crime event.")
        for index, row in crime_data.iterrows():
            folium.Marker([row['latitude'], row['longitude']], popup=row['location']).add_to(marker_cluster)
            folium.CircleMarker([row['latitude'], row['longitude']], radius=row["fatalities"] / 10, color='red', fill_color='red').add_to(nigeria_map)

        # let the user choose to display the map or not
        if st.checkbox('Show Map'):
            st_folium(nigeria_map, width=1500, height=500)
    except requests.exceptions.RequestException as e:
        st.error("Error fetching crime events data: {}".format(e))

def predict_crime(date, state):
    try:
        response = requests.get(BASE_URL + "predict", params={"date": date, "state": state})
        response.raise_for_status()
        data = response.json()["data"]
        return data["crime_prediction"], data["probability"]
    except requests.exceptions.RequestException as e:
        st.error("Error fetching crime prediction: {}".format(e))
        return None, None

def crime_prediction_page():
    st.title("Crime Prediction")
    # add a disclaimer
    st.info("Please note that this is a prediction and not a guarantee. The prediction is based on historical data and machine learning algorithms.")
    date = st.date_input("Select Date", value=datetime.now())
    state = st.selectbox("Select State", st.session_state.states[1:])

    if st.button("Predict Crime Rate"):
        if date and state:
            prediction, probability = predict_crime(date, state)
            if prediction is not None:
                if prediction == 1:
                    st.error(f"There is a {probability * 100}% probability of a crime incident occurring in {state} on {date}.")
                else:
                    st.success(f"There is a {probability * 100}% probability of no crime incident occurring in {state} on {date}.")

def get_latest_crime(limit=10, state=None, actor1=None):
    try:
        params = {"limit": limit}
        if state:
            params["state"] = state
        if actor1:
            params["actor1"] = actor1
        
        response = requests.get(BASE_URL + "incidents/latest", params=params)
        response.raise_for_status()
        return response.json()["data"]
    except requests.exceptions.RequestException as e:
        st.error("Error fetching latest crime incidents: {}".format(e))
        return None

                
def latest_crime_page():
    st.title("Latest Crime Incidents")

    limit = st.number_input("Number of incidents to retrieve", min_value=1, max_value=100, value=10)
    state = st.selectbox("Select State (Optional)", st.session_state.states[:])
    actor1 = st.selectbox("Select Actor (Optional)", st.session_state.actors[:])
    if actor1 == "All":
        actor1 = None
    if state == "All":
        state = None

    if st.button("Get Latest Crimes"):
        latest_crimes = get_latest_crime(limit, state, actor1)
        if latest_crimes:
            st.write(f"Number of incidents retrieved: {len(latest_crimes)}")
            for crime in latest_crimes:
                st.error(
                    f"""
                ### {crime['event_date']}
                - **Location:** {crime['location']}, {crime['admin1']}
                - **Notes:** :green[{crime['notes']}]
                - **Source:** {crime['source']}
                """)
        else:
            st.warning("No data available to display.")
                
                
def report_crime_page():
    st.subheader('Report a Crime')

    form = st.form(key='report_crime')
    # select state
    state = form.selectbox('Select State', st.session_state.states[1:])
    # input LGA
    lga = form.text_input('Enter LGA')
    # select perpetrator
    perpetrator = form.selectbox(
        'Select Perpetrator', st.session_state.actors)
    # add a text area to the page
    report = form.text_area('Enter your report here')
    # add a toggle to be anonymous or not
    anonym = form.checkbox('Be Anonymous')
    # if the user wants to be anonymous, add a text input to enter a name

    name = contact = None
    if not anonym:
        name = form.text_input('Enter your name')
        contact = form.text_input('Enter your contact')

    submit = form.form_submit_button('Report')

    if submit:
        created_at = str(datetime.now())
        # TODO: send the report to the backend
        return report_submitted_page(state, lga, perpetrator, name, contact)

    return False


def report_submitted_page(state, lga, perpetrator, name=None, contact=None):
    st.subheader('Report Submitted')
    # add a text to the page
    st.info('Your report has been submitted. Thank you for your contribution.')
    # add a link to the home page

    return state, lga, perpetrator, name, contact

def get_crime_change_by_event_type(location, base, reference_date=None):
    try:
        params = {"location": location, "base": base}
        if reference_date:
            params["reference_date"] = reference_date
        response = requests.get(BASE_URL + "crime_change_by_event_type", params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error("Error fetching crime change by event type: {}".format(e))
        return None

def get_crime_change_by_actor(location, base, reference_date=None):
    try:
        params = {"location": location, "base": base}
        if reference_date:
            params["reference_date"] = reference_date
        response = requests.get(BASE_URL + "crime_change_by_actor", params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error("Error fetching crime change by actor: {}".format(e))
        return None

def get_crime_change_percentage(location=None, base="year", reference_date=None):
    try:
        params = {"base": base}
        if location:
            params["location"] = location
        if reference_date:
            params["reference_date"] = reference_date
        response = requests.get(BASE_URL + "crime_change_percentage", params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error("Error fetching crime change percentage: {}".format(e))
        return None

def dynamic_analysis_page():
    st.title("Dynamic Crime Analysis")

    analysis_type = st.selectbox("Select Analysis Type", ["Event Type Change", "Actor Change"])
    location = st.selectbox("Select Location", st.session_state.states[1:])
    base = st.selectbox("Select Base Period", ["year", "month", "week", "day"])
    reference_date = st.date_input("Select Reference Date (Optional)", value=None)

    if st.button("Analyze"):
        if not location:
            st.warning("Please provide a location.")
            return

        reference_date_str = reference_date.strftime('%Y-%m-%d') if reference_date else None
        
        if analysis_type == "Event Type Change":
            data = get_crime_change_by_event_type(location, base, reference_date_str)
            if not data:
                st.warning("No data available to display.")
                return
            # get leng of data
            data_len = len(data)
            # We need four columns per line, so we shall have data_len/4 lines
            num_lines = data_len // 3
            # We need to add one more line if there is a remainder
            if data_len % 3:
                num_lines += 1
            # Loop through the data and display it in columns
            for i in range(num_lines):
                col1, col2, col3 = st.columns(3)
                for j in range(3):
                    index = i * 3 + j
                    if index < data_len:
                        item = data[index]
                        col = col1 if j == 0 else col2 if j == 1 else col3
                        change_percentage = item['change_percentage']
                        if change_percentage in ["N/A", "NA"]:
                            change_percentage = 0
                        change_percentage = float(change_percentage)

                        arrow = "▼" if change_percentage < 0 else "▲"
                        color = "lightgreen" if change_percentage < 0 else "lightcoral"
                        if change_percentage == 0:
                            color = "lightblue"

                        col.markdown(f"""
                        <div style="border: 1px solid {color}; padding: 10px; border-radius: 5px; background-color: {color};">
                            <p><b>{item['event_type']}</b></p>
                            <p><b>{arrow} {change_percentage}%</b></p>
                            <p><b>Current Count:</b> {item['current_count']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                # create a space between the rows
                st.markdown("---")
        
        elif analysis_type == "Actor Change":
            data = get_crime_change_by_actor(location, base, reference_date_str)
            if not data:
                st.warning("No data available to display.")
                return
            # get leng of data
            data_len = len(data)
            # We need four columns per line, so we shall have data_len/4 lines
            num_lines = data_len // 3
            # We need to add one more line if there is a remainder
            if data_len % 3:
                num_lines += 1
            # Loop through the data and display it in columns
            for i in range(num_lines):
                col1, col2, col3 = st.columns(3)
                for j in range(3):
                    index = i * 3 + j
                    if index < data_len:
                        item = data[index]
                        col = col1 if j == 0 else col2 if j == 1 else col3
                        change_percentage = item['change_percentage']
                        if change_percentage in ["N/A", "NA"]:
                            change_percentage = 0
                        change_percentage = float(change_percentage)

                        arrow = "▼" if change_percentage < 0 else "▲"
                        color = "lightgreen" if change_percentage < 0 else "lightcoral"
                        if change_percentage == 0:
                            color = "lightblue"

                        col.markdown(f"""
                        <div style="border: 1px solid {color}; padding: 10px; border-radius: 5px; background-color: {color};">
                            <p><b>{item['actor1']}</b></p>
                            <p><b>{arrow} {change_percentage}%</b></p>
                            <p><b>Current Count:</b> {item['current_count']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                # create a space between the rows
                st.markdown("---")
                
        
        elif analysis_type == "Crime Change Percentage":
            data = get_crime_change_percentage(location, base, reference_date_str)
            print(data)
            if not data:
                st.warning("No data available to display.")
                return
            # get leng of data
            data_len = len(data)
            # We need four columns per line, so we shall have data_len/4 lines
            num_lines = data_len // 3
            # We need to add one more line if there is a remainder
            if data_len % 3:
                num_lines += 1
            # Loop through the data and display it in columns
            for i in range(num_lines):
                col1, col2, col3 = st.columns(3)
                for j in range(3):
                    index = i * 3 + j
                    if index < data_len:
                        item = data[index]
                        col = col1 if j == 0 else col2 if j == 1 else col3
                        change_percentage = item['change_percentage']
                        if change_percentage in ["N/A", "NA"]:
                            change_percentage = 0
                        change_percentage = float(change_percentage)

                        arrow = "▼" if change_percentage < 0 else "▲"
                        color = "lightgreen" if change_percentage < 0 else "lightcoral"
                        if change_percentage == 0:
                            color = "lightblue"

                        col.markdown(f"""
                        <div style="border: 1px solid {color}; padding: 10px; border-radius: 5px; background-color: {color};">
                            <p><b>{item['location']}</b></p>
                            <p><b>{arrow} {change_percentage}%</b></p>
                            <p><b>Current Count:</b> {item['current_count']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                # create a space between the rows
                st.markdown("---")


def main():
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Crime Overview", "Crime Prediction", "Latest Crime Incidents", "Report Crime", "Dynamic Analysis"])
    st.header(":flag-ng: NIGERIA CRIME INCIDENCE DASHBOARD")
    
    # check if the server is running
    status = check_server_status()
    if status != 200:
        st.error("The server is currently down. Please try again later.")
        return
    
    if page == "Crime Overview":
        crime_overview()
        section_break()
        plot_historical_bar()
        plot_historical_line()
        section_break()
        display_country_map()
    elif page == "Crime Prediction":
        crime_prediction_page()
    elif page == "Latest Crime Incidents":
        latest_crime_page()
    elif page == "Report Crime":
        report_crime_page()
    elif page == "Dynamic Analysis":
        dynamic_analysis_page()

if __name__ == "__main__":
    main()
