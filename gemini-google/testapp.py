import os
import flet as ft
import google.generativeai as genai
import random
from transcriber import produce_voice
import numpy as np
import sounddevice as sd
import threading
import queue
import requests
import pandas as pd
import numpy as np
from typing import List
from fuzzywuzzy import process
import json
from api_calls import police_feed, trafikverket_call
# from tools_gemini_functions import get_traffic_data, get_cameras, get_police_events


def get_closest_match(query, choices):
    """
    Find the closest match for the query in the list of choices using fuzzy matching.
    
    Args:
        query (str): The query string to match.
        choices (list of str): The list of possible matches.
        
    Returns:
        str: The closest matching string from choices.
    """
    match, score = process.extractOne(query, choices)
    return match
    
def get_police_events(crime_type: List[str]=[], location_name: List[str]=[], crime_date: List[str]=[]):
    """
    Function that grabs crime reports, crime feed, police feed from Swedish Police, also known as Polisen.
    This allows the requester to get the type of crime from the Police events dataframe, filter on location, get the latitude and longitude,
    the summary of the event, and get the date as well. The function is filtering regardless if provided with something or not.

    Args:
        crime_type: the type of crime they want to filter on. If they don't provide a filter then they want the whole dataframe.
        location_name: the location they want to filter on
        crime_date: the date they want to filter on. In the format YYYY-MM-DD as a string.
    
    Returns:
        filtered_data: a filtered dataframe
    """
    global police_events
    police_df = police_events.copy().drop(columns="id")
    
    if crime_type:
        police_df = police_df[police_df.type.isin(crime_type)]
    
    if location_name:
        unique_locations = police_df["location.name"].unique().tolist()
        matched_locations = [get_closest_match(loc, unique_locations) for loc in location_name]
        police_df = police_df[police_df["location.name"].isin(matched_locations)]
    
    if crime_date:
        police_df['datetime'] = pd.to_datetime(police_df['datetime']).dt.strftime('%Y-%m-%d')
        police_df = police_df[police_df["datetime"].isin(crime_date)]

    return police_df.to_json(force_ascii=False)


def get_cameras():
    """
    This allows the requester to get a list of all available cameras if they do not know which camera they want.
    You must provide them with a cleaned up version of the returned list such that it works in a Markdown setting.

    """
    return olyckor.Name.sort_values().unique().tolist()


def get_traffic_data(camera: str, date_to_filter: str) -> str:
    """
    Allows the requester to grab image from Trafikverket cameras and filter on date.
    This utilizes an API call which has been pre-fetched and stored in a pandas dataframe called 'olyckor'.
    The user can define which camera and which date they want to filter.
    You must display the image by using Markdown, for instance ![The Camera](URL_OF_THE_IMAGE). The URL is returned by this function.
    If you did not find the camera location you must tell the user that you didn't find it and that you chose a random location for them.

    Args:
        camera: Name of the location for the camera. If not defined exactly, help the user to the most similar one. String format.
        date_to_filter: Date of the PhotoTime. In the format YYYY-MM-DD as a string.


    Returns:
        The URL of the image.
    """
    global olyckor
    olyckor = olyckor[olyckor.Active == True]
    olyckor["PhotoTime"] = pd.to_datetime(olyckor["PhotoTime"], utc=True)
    olyckor['PhotoTime'] = olyckor.PhotoTime.dt.strftime('%Y-%m-%d %H:%M')

    AVAILABLE_CAMERAS = olyckor.Name.unique()
    unique_cameras = AVAILABLE_CAMERAS.tolist()
    matched_cameras = get_closest_match(camera, unique_cameras) 

    if camera in AVAILABLE_CAMERAS:

        vg = olyckor[olyckor.Name == matched_cameras]
        vg = vg[vg["PhotoTime"] > date_to_filter]
        vg["PhotoUrl"] = np.where(vg.HasFullSizePhoto == True, vg.PhotoUrl+"?type=fullsize", vg.PhotoUrl)
        return vg["PhotoUrl"].iloc[0]
    
    else:
        # INSTRUCTION: TELL THE USER THAT YOU DID NOT FIND THE CAMERA LOCATION THEY DESIRED SO YOU GRABBED A RANDOM ONE
        random_camera = np.random.choice(AVAILABLE_CAMERAS)
        vg = olyckor[olyckor.Name == random_camera]
        vg = vg[vg["PhotoTime"] > date_to_filter]
        vg["PhotoUrl"] = np.where(vg.HasFullSizePhoto == True, vg.PhotoUrl+"?type=fullsize", vg.PhotoUrl)
        return vg["PhotoUrl"].iloc[0]

df = pd.DataFrame({"time": [1,2,3,4,5,6], "stock_price": [273, 434, 323, 389, 500, 280]})
NYCKELN = os.environ.get('GOOGLE_API_KEY')

class TimeSeries(ft.UserControl):
    def __init__(self):
        self.data_points = []
        self.points = df

        self.chart = ft.LineChart(
            tooltip_bgcolor = ft.colors.with_opacity(0.7, ft.colors.WHITE),
            expand=True,
            min_y = min(df.stock_price),
            max_y = max(df.stock_price),
            min_x = min(df.time),
            max_x = max(df.time),
            left_axis = ft.ChartAxis(labels_size=50),
            bottom_axis = ft.ChartAxis(labels_size=40, labels_interval=1)
        )

    def build(self):
        self.chart.data_series = []
        return ft.Column(
            horizontal_alignment = "center",
            controls=[
                ft.Text("Test graph", size=16, weight="bold"),
                self.chart,
            ]
        )


async def main(page: ft.Page):
    chart = TimeSeries()
    is_mobile = False

    def detect_mobile(e):
        nonlocal is_mobile
        is_mobile = e.data
        setup_audio_system()

    def setup_audio_system():
        if is_mobile:
            setup_mobile_audio()
        else:
            setup_desktop_audio()
        page.update()

    def setup_mobile_audio():
        nonlocal on_microphone_click
        page.on_view_pop = lambda _: page.window_js_eval(mobile_js_code)
        on_microphone_click = lambda _: page.window_js_eval("toggleRecording()")


    def setup_desktop_audio():
        nonlocal on_microphone_click
        on_microphone_click = on_microphone_click

    def handle_audio_data(e):
        audio_data = base64.b64decode(e.data.split(',')[1])
        audio_array = np.frombuffer(audio_data, dtype=np.float32)
        process_audio(audio_array)

    mobile_js_code = """
    let mediaRecorder;
    let audioChunks = [];

    async function toggleRecording() {
        if (!mediaRecorder || mediaRecorder.state === "inactive") {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                const reader = new FileReader();
                reader.onloadend = () => {
                    window.flutter_inappwebview.callHandler('audio_data', reader.result);
                };
                reader.readAsDataURL(audioBlob);
            };

            mediaRecorder.start();
            window.flutter_inappwebview.callHandler('update_button', 'recording');
        } else {
            mediaRecorder.stop();
            window.flutter_inappwebview.callHandler('update_button', 'not_recording');
        }
    }
    """

    global olyckor
    global police_events
    olyckor = trafikverket_call()
    police_events = police_feed()
    

    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

    helper_fns = [get_traffic_data, get_cameras, get_police_events]
    model = genai.GenerativeModel('gemini-1.5-flash-002',tools=helper_fns)
    history = []
    chatdialog = model.start_chat(history=history, enable_automatic_function_calling=True)
    page.title = "Dashboard App"
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = "adaptive"

    def generate_random_data(num_points=10):
        return [random.randint(0, 100) for _ in range(num_points)]

    def update_chart(e):
        chart.data = generate_random_data()
        page.update()

    menubar = ft.AppBar(
        leading=ft.IconButton(icon=ft.icons.MENU),
        title=ft.Text("Dashboard"),
        center_title=False,
    )

    api_feed_icon = ft.IconButton(
        icon=ft.icons.REFRESH,
        on_click=update_chart,
        tooltip="Refresh API Feed",
    )

    chart = ft.LineChart(
        data=generate_random_data(),
        width=300,
        height=200,
        tooltip_bgcolor=ft.colors.with_opacity(0.8, ft.colors.WHITE),
        expand=True,
    )

    gauge = ft.ProgressRing(
        value=0.5,
        width=150,
        height=150,
        tooltip="Screen Time: 70% of Weekly Total",
    )

    chart_container = ft.Container(
        content=ft.Row([gauge, chart]),
        padding=10,
        border_radius=10,
        bgcolor=ft.colors.with_opacity(0.1, ft.colors.WHITE),
    )

    api_feed_b = ft.IconButton(
        icon=ft.icons.ADD_CHART,
        tooltip="Show another API Feed",
    )

    camera_button = ft.IconButton(
        icon=ft.icons.CAMERA_ALT,
        tooltip="Open Camera",
    )

    def on_message(message):
        chat.controls.append(ft.Markdown(f"Gemini: {message}"))
        page.update()

    def send_message(e):
        user_message = chat_input.value
        if user_message:
            chat.controls.append(ft.Text(f"You: {user_message}"))
            chat_input.value = ""
            page.update()

            response = chatdialog.send_message(user_message)
            on_message(response.text)


    def start_listening(e):
        microphone_button.icon = ft.icons.MIC_OFF
        microphone_button.tooltip = "Stop listening"
        page.update()
        # Implement actual microphone listening and transcription here

    def stop_listening(e):
        microphone_button.icon = ft.icons.MIC
        microphone_button.tooltip = "Start listening"
        page.update()
        # Implement stopping the microphone and sending transcription to LLM

    microphone_button = ft.IconButton(
        icon=ft.icons.MIC,
        tooltip="Start listening",
        on_click=lambda e: start_listening(e) if microphone_button.icon == ft.icons.MIC else stop_listening(e),
    )

    audio_queue = queue.Queue()
    recording = False
    audio_thread = None
    SAMPLE_RATE = 44100

    def audio_callback(indata, frames, time, status):
        if status:
            print(status)
        audio_queue.put(indata.copy())

    def start_recording():
        nonlocal recording, audio_thread
        recording = True
        audio_thread = threading.Thread(target=record_audio)
        audio_thread.start()

    def stop_recording():
        nonlocal recording
        recording = False
        if audio_thread:
            audio_thread.join()

    def record_audio():
        with sd.InputStream(callback=audio_callback, channels=1, samplerate=SAMPLE_RATE):
            while recording:
                sd.sleep(100)

    def get_audio_array():
        audio_data = []
        while not audio_queue.empty():
            audio_data.append(audio_queue.get())
        if audio_data:
            return np.concatenate(audio_data, axis=0)
        return None
    


    def on_microphone_click(e):
        nonlocal recording
        if not recording:
            microphone_button.icon = ft.icons.MIC_OFF
            microphone_button.tooltip = "Stop recording"
            start_recording()
        else:
            microphone_button.icon = ft.icons.MIC
            microphone_button.tooltip = "Start recording"
            stop_recording()
            # global audio_array
            audio_array = get_audio_array()
            if audio_array is not None:
                # Here you would typically send this numpy array to your transcriber
                # For demonstration, we'll just add a message to the chat
                # global audiotranslation
                audiotranslation = produce_voice(audio_array)
                chat.controls.append(ft.Text(f"Transcription: {audiotranslation}"))
                user_message = audiotranslation
                if user_message:
                    # chat.controls.append(ft.Text(f"You: {user_message}"))
                    chat_input.value = ""
                    page.update()
                    response = chatdialog.send_message(user_message)
                    on_message(response.text)

            else:
                chat.controls.append(ft.Text("No audio recorded"))
        page.update()

    page.on_web_event = handle_audio_data

    microphone_button = ft.IconButton(
        icon=ft.icons.MIC,
        tooltip="Start recording",
        on_click=on_microphone_click,
    )

    chat = ft.Column(scroll=ft.ScrollMode.AUTO)
    chat_input = ft.TextField(hint_text="Type a message...", expand=True, on_submit=send_message)
    send_button = ft.IconButton(icon=ft.icons.SEND, on_click=send_message)

    chat_container = ft.Container(
        content=ft.Column([
            chat,
            ft.Row([microphone_button, chat_input, send_button]),
        ]),
        padding=10,
        expand=True,
    )



    page.add(
        menubar,
        ft.Row([api_feed_icon, api_feed_b, camera_button], alignment=ft.MainAxisAlignment.SPACE_AROUND),
        chart_container,
        chat_container,
        # ft.Row([microphone_button, chat_input, send_button]),
    )

    # Detect if running on mobile
    page.on_view_pop = lambda _: page.window_js_eval("""
    window.flutter_inappwebview.callHandler('detect_mobile', /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent));
    """)

    page.on_web_event = detect_mobile

ft.app(target=main)