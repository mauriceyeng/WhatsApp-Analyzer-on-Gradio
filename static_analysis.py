import gradio as gr
import pandas as pd
import plotly.graph_objs as go

# Load the data
data_path = 'C:\\Users\\mauri\\Documents\\EWYL_analyzer\\390.csv'
df = pd.read_csv(data_path)

# Ensure the date column is a datetime type
df['date'] = pd.to_datetime(df['date'])

def update_data(group, start_date, end_date):
    # Process dates and filter data
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    mask = (df['group'] == group) & (df['date'] >= start_date) & (df['date'] <= end_date)
    filtered_data = df[mask]

    # Convert datetime objects to string format for the table
    filtered_table_data = filtered_data.copy()
    filtered_table_data['date'] = filtered_table_data['date'].dt.strftime('%Y-%m-%d')

    return filtered_table_data

def update_plot(group, start_date, end_date):
    # Process dates and filter data for plot
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    mask = (df['group'] == group) & (df['date'] >= start_date) & (df['date'] <= end_date)
    filtered_data = df[mask]

    # Plotting the graph
    fig = go.Figure()
    for metric, name in zip(['M - W/A txt count', 'S - W/A txt count', 'M - WATI count', 'S - WATI count'],
                            ['Mentor WA Texts', 'Student WA Texts', 'Mentor WATI Count', 'Student WATI Count']):
        fig.add_trace(go.Scatter(x=filtered_data['date'], y=filtered_data[metric], mode='lines', name=name))

    fig.update_layout(title='Communication Metrics Over Time',
                      xaxis_title='Date',
                      yaxis_title='Count',
                      legend_title='Metric')

    return fig

def analyze_data(group, start_date, end_date):
    # Process dates and filter data
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    mask = (df['group'] == group) & (df['date'] >= start_date) & (df['date'] <= end_date)
    filtered_data = df[mask]

    # Total count of messages for mentors and students
    mentor_total = filtered_data['M - W/A txt count'].sum() + filtered_data['M - WATI count'].sum()
    student_total = filtered_data['S - W/A txt count'].sum() + filtered_data['S - WATI count'].sum()
    
    # Average messages per day for mentors and students
    total_days = (end_date - start_date).days + 1  # inclusive of end date
    avg_mentor_messages = mentor_total / total_days
    avg_student_messages = student_total / total_days

    # Days with zero conversations
    zero_conversation_days = filtered_data[(filtered_data['M - W/A txt count'] == 0) & 
                                           (filtered_data['S - W/A txt count'] == 0) &
                                           (filtered_data['M - WATI count'] == 0) & 
                                           (filtered_data['S - WATI count'] == 0)].shape[0]

    # More active party
    most_active = "Mentor" if mentor_total > student_total else "Student"

    # Basic statistics
    min_mentor_messages = filtered_data[['M - W/A txt count', 'M - WATI count']].min().min()
    max_mentor_messages = filtered_data[['M - W/A txt count', 'M - WATI count']].max().max()
    min_student_messages = filtered_data[['S - W/A txt count', 'S - WATI count']].min().min()
    max_student_messages = filtered_data[['S - W/A txt count', 'S - WATI count']].max().max()

    # Prepare the summary text
    summary_text = f"Number of days with zero conversations: {zero_conversation_days}\n"
    summary_text += f"Total messages sent by Mentor: {mentor_total}\n"
    summary_text += f"Total messages sent by Student: {student_total}\n"
    summary_text += f"Average messages sent by Mentor per day: {avg_mentor_messages:.2f}\n"
    summary_text += f"Average messages sent by Student per day: {avg_student_messages:.2f}\n"
    summary_text += f"Most messages sent by: {most_active}\n"
    summary_text += f"Minimum messages by Mentor in a day: {min_mentor_messages}\n"
    summary_text += f"Maximum messages by Mentor in a day: {max_mentor_messages}\n"
    summary_text += f"Minimum messages by Student in a day: {min_student_messages}\n"
    summary_text += f"Maximum messages by Student in a day: {max_student_messages}\n"

    return summary_text


# Define the blocks
with gr.Blocks() as blocks:
    # Create a row of inputs
    with gr.Row():
        group_dropdown = gr.Dropdown(choices=sorted(df['group'].unique()), label="Select a Group")
        start_date_input = gr.Textbox(label="Enter start date (YYYY-MM-DD)", value=str(df['date'].min().date()))
        end_date_input = gr.Textbox(label="Enter end date (YYYY-MM-DD)", value=str(df['date'].max().date()))
        submit_button = gr.Button("Submit")
    
    # Create the output components
    output_table = gr.Dataframe()
    output_graph = gr.Plot()
    output_summary = gr.Textbox(label="Summary Statistics")

    # Function call
    submit_button.click(
        fn=lambda group, start_date, end_date: (update_data(group, start_date, end_date), 
                                                update_plot(group, start_date, end_date), 
                                                analyze_data(group, start_date, end_date)),
        inputs=[group_dropdown, start_date_input, end_date_input],
        outputs=[output_table, output_graph, output_summary]
    )

# Launch the interface
blocks.launch()
