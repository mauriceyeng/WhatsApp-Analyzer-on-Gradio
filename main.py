import io
import os.path
import pickle
import gradio as gr
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Scopes required by the app
SCOPES = ['https://www.googleapis.com/auth/drive']

def authenticate():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('creds.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
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
        print('No files found.')
        return None
    else:
        latest_file = items[0]
        print(f'Latest file: {latest_file["name"]} (ID: {latest_file["id"]})')
        return latest_file

def download_file(service, file_id, file_name):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()
        print("Download Progress: {0}%".format(int(status.progress() * 100)))

    fh.seek(0)
    with open(file_name, 'wb') as f:
        f.write(fh.read())
    print(f'{file_name} downloaded successfully.')

import re

def summarize_chat(file_name):
    mentor_latest = None
    student_latest = None
    unique_dates = set()
    
    # Regular expression pattern for matching lines with date, time, hyphen, sender, and message_body
    # This pattern ensures it captures lines that start with a date in 'MM/DD/YY, HH:MM am/pm' format, followed by the sender and message.
    pattern = r"^\d{2}/\d{2}/\d{2}, \d{1,2}:\d{2} [ap]m - .*?: .*?$"
    
    with open(file_name, 'r', encoding='utf-8') as file:
        for line in file:
            if re.match(pattern, line):  # Check if line matches the pattern
                date_time_part, message_part = line.split(' - ', 1)
                date = date_time_part.split(',')[0].strip()
                unique_dates.add(date)
                
                sender_message = message_part.split(': ', 1)
                if len(sender_message) < 2:
                    continue  # Skip lines that don't have a proper sender and message split

                sender = sender_message[0].strip()
                # Check if sender is a mentor (alphabetical sender name) or student (starts with '+')
                if sender.isalpha():
                    mentor_latest = date
                elif sender.startswith('+') and sender[1:].isdigit():
                    student_latest = date
    
    summary = f"Latest message by mentor/counselor: {mentor_latest}\nLatest message by student: {student_latest}\nUnique conversation days in last 30 days: {len(unique_dates)}"
    return summary



def fetch_and_summarize(name_pattern):
    service = authenticate()
    file_info = search_latest_file(service, name_pattern)
    if file_info:
        download_file(service, file_info['id'], file_info['name'])
        text_content = open(file_info['name'], 'r', encoding='utf-8').read()
        summary = summarize_chat(file_info['name'])
        return text_content, summary
    else:
        return "File not found."

def main():
    input_box = gr.Textbox(label="Enter the file name pattern")
    submit_button = gr.Button()

    text_file = gr.Textbox(label="Text File", type="text", lines=20)
    summary_box = gr.Textbox(label="Summary", type="text", lines=10)

    def process_file(name_pattern):
        text, summary = fetch_and_summarize(name_pattern)
        return text, summary

    gr.Interface(fn=process_file, inputs=input_box, outputs=[text_file, summary_box], title="Google Drive Chat Summary", description="Enter a pattern to search for the latest chat file in Google Drive and view its summary.").launch()

if __name__ == '__main__':
    main()
