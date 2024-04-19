import io
import os
import pickle
import pandas as pd
import re
import gradio as gr
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go



SCOPES = ['https://www.googleapis.com/auth/drive']

def authenticate():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('creds.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('drive', 'v3', credentials=creds)

def search_latest_file(service, name_pattern):
    results = service.files().list(
        q=f"name contains '{name_pattern}' and mimeType='text/plain'",
        spaces='drive',
        fields='files(id, name, createdTime)',
        orderBy='createdTime desc',
        pageSize=1  # Fetch only the most recent file
    ).execute()
    items = results.get('files', [])
    if not items:
        return None
    else:
        return items[0]

def download_file(service, file_id, file_name):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    with open(file_name, 'wb') as f:
        f.write(fh.read())
    return file_name

def extract_data(file_name):
    # Regular expression to capture date, time, sender, and message
    pattern = r"^(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2}\s?[apAP][mM]) - (.*?): (.*)"

    data = []
    current_entry = None
    with open(file_name, 'r', encoding='utf-8') as file:
        for line in file:
            match = re.match(pattern, line)
            if match:
                if current_entry:
                    data.append(current_entry)
                date, time, sender, message = match.groups()
                # Determine if sender is a mentor or student based on the presence of digits
                sender_label = 'Mentor' if not any(char.isdigit() for char in sender) else 'Student'
                current_entry = [f'{date}, {time}', sender_label, message]
            else:  # Append continuation of messages to the last message
                if current_entry:
                    current_entry[2] += " " + line.strip()
                else:
                    print(f'Line skipped (no previous message to attach to): {line}')

    if current_entry:
        data.append(current_entry)  # Append the last entry if the loop ends

    df = pd.DataFrame(data, columns=['Date', 'Sender', 'Message'])
    if df.empty:
        print("No data extracted from the file. Check the regular expression and file format.")
        return df

    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%y, %I:%M %p', errors='coerce')
    invalid_dates = df[df['Date'].isnull()]
    if not invalid_dates.empty:
        print(f"Rows with invalid DateTime format: {invalid_dates}")
    df = df.dropna(subset=['Date'])
    df.sort_values('Date', inplace=True)

    return df

def create_plot(plot_data):
    # Create a plot using the plot_data
    plt.figure()
    plt.plot(plot_data)  # Assuming plot_data is a list of y-values. Adjust as needed.
    plt.title("Daily Message Volume")
    # Convert the plot to JSON using Gradio's functionality
    return gr.Matplotlib(fig)

def analyze_chat_data(df):
    print("Starting analysis...")
    if df.empty:
        print("DataFrame is empty after data extraction.")
        return "No data available", pd.DataFrame(), None

    try:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date'])
        df.set_index('Date', inplace=True)

        # Determine the start and end dates from the DataFrame
        start_date = df.index.min()
        end_date = df.index.max()

        mentor_counts = df[df['Sender'] == 'Mentor'].resample('D').count()['Message']
        student_counts = df[df['Sender'] == 'Student'].resample('D').count()['Message']

        total_mentor_messages = mentor_counts.sum()
        total_student_messages = student_counts.sum()
        avg_mentor_messages = mentor_counts.mean() if not mentor_counts.empty else 0
        avg_student_messages = student_counts.mean() if not student_counts.empty else 0
        zero_conversation_days = (mentor_counts + student_counts == 0).sum()
        most_active = "Mentor" if total_mentor_messages > total_student_messages else "Student"

        # Update the summary text to include start and end dates
        summary_text = (f"Chat Start Date: {start_date.strftime('%Y-%m-%d')}\n"
                        f"Chat End Date: {end_date.strftime('%Y-%m-%d')}\n"
                        f"Number of days with zero conversations: {zero_conversation_days}\n"
                        f"Total messages sent by Mentor: {total_mentor_messages}\n"
                        f"Total messages sent by Student: {total_student_messages}\n"
                        f"Average messages sent by Mentor per day: {avg_mentor_messages:.2f}\n"
                        f"Average messages sent by Student per day: {avg_student_messages:.2f}\n"
                        f"Most messages sent by: {most_active}\n")

        # Creating the Plotly plot
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=mentor_counts.index, y=mentor_counts.values,
                                 mode='lines', name='Mentor Messages',
                                 line=dict(color='green', width=1)))
        fig.add_trace(go.Scatter(x=student_counts.index, y=student_counts.values,
                                 mode='lines', name='Student Messages',
                                 line=dict(color='red', width=1)))

        fig.update_layout(title='Daily Message Volume by Sender Type',
                          xaxis_title='Date',
                          yaxis_title='Number of Messages',
                          legend_title='Sender Type')

        return summary_text, df, fig

    except Exception as e:
        print(f"An error occurred during analysis: {e}")
        return f"An error occurred: {e}", pd.DataFrame(), None

def setup_interface():
    with gr.Blocks() as app:
        with gr.Row():
            name_input = gr.Textbox(label="Enter the file name pattern")
            submit_button = gr.Button("Analyze")
        output_file = gr.Textbox(label="File Name")  # Display only, users cannot edit
        output_summary = gr.Textbox(label="Analysis Summary", lines=10)  # Users can view but not edit directly
        output_plot = gr.Plot(label="Daily Message Volume")
        output_text = gr.Textbox(label="Full Text File", lines=10, type="text")  # Display large text

        submit_button.click(
            fn=fetch_and_analyze,
            inputs=[name_input],
            outputs=[output_file, output_summary, output_plot, output_text]
        )
    return app

app = setup_interface()
app.launch()