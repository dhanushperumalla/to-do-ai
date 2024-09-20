import streamlit as st
import pandas as pd
import os
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
import hashlib
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import utc

# Initialize the Groq model
groq_api_key = st.secrets["GROQ_API_KEY"]
model = ChatGroq(model="Gemma2-9b-It", groq_api_key=groq_api_key)

# File to store tasks and users
TASKS_FILE = "tasks.csv"
USERS_FILE = "users.csv"

# Initialize the files if they don't exist or are empty
def initialize_file(file_path, columns):
    if not os.path.exists(file_path) or os.stat(file_path).st_size == 0:
        pd.DataFrame(columns=columns).to_csv(file_path, index=False)

# Initialize files
initialize_file(TASKS_FILE, ['User', 'Task', 'Category', 'Priority', 'Completed', 'Description', 'ScheduledDate', 'ScheduledTime'])
initialize_file(USERS_FILE, ['Username', 'PasswordHash'])

# Load tasks from the CSV file
def load_tasks():
    try:
        df = pd.read_csv(TASKS_FILE)
        if 'User' not in df.columns:
            df['User'] = 'Unknown'  # Add 'User' column if it doesn't exist
        return df
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=['User', 'Task', 'Category', 'Priority', 'Completed', 'Description', 'ScheduledDate', 'ScheduledTime'])

# Save tasks to the CSV file
def save_tasks(df):
    df.to_csv(TASKS_FILE, index=False)

# Load users from the CSV file
def load_users():
    try:
        return pd.read_csv(USERS_FILE)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=['Username', 'PasswordHash'])

# Save users to the CSV file
def save_users(df):
    df.to_csv(USERS_FILE, index=False)

# Hash password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Authenticate user
def authenticate(username, password):
    users = load_users()
    user = users[users['Username'] == username]
    if not user.empty:
        if user.iloc[0]['PasswordHash'] == hash_password(password):
            return True
    return False

# Register new user
def register_user(username, password):
    users = load_users()
    if username in users['Username'].values:
        return False
    new_user = pd.DataFrame({'Username': [username], 'PasswordHash': [hash_password(password)]})
    users = pd.concat([users, new_user], ignore_index=True)
    save_users(users)
    return True

# Prompt template for AI description
description_template = PromptTemplate(
    input_variables=["task", "category", "priority"],
    template="""
    Generate a brief, motivating description for the following task:
    Task: {task}
    Category: {category}
    Priority: {priority}

    The description should:
    1. Explain the importance or potential impact of the task
    2. Provide a quick tip or strategy for accomplishing it
    3. Be concise (2-3 Bullet points max)
    4. Be encouraging and positive in tone

    Description:
    """
)

# Generate AI description
def generate_ai_description(task, category, priority):
    prompt = description_template.format(task=task, category=category, priority=priority)
    response = model.invoke(prompt)
    return response.content

# Schedule notification
def schedule_notification(task, scheduled_date, scheduled_time):
    scheduled_datetime = datetime.datetime.combine(scheduled_date, scheduled_time)
    scheduled_datetime = utc.localize(scheduled_datetime)  # Make scheduled_datetime timezone-aware
    current_time = datetime.datetime.now(utc)
    notification_time = scheduled_datetime - datetime.timedelta(hours=1)
    if notification_time > current_time:
        scheduler.add_job(send_notification, 'date', run_date=notification_time, args=[task])

# Send notification
def send_notification(task):
    st.warning(f"Reminder: Task '{task}' is due in 1 hour!")

# Initialize scheduler
scheduler = BackgroundScheduler(timezone=utc)
scheduler.start()

# UI for the app
def todo_app():
    st.title("AI-based To-Do List with Task Descriptions")

    # Authentication
    if 'user' not in st.session_state:
        st.session_state.user = None

    if not st.session_state.user:
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        
        with tab1:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit_button = st.form_submit_button("Login")
                if submit_button:
                    if authenticate(username, password):
                        st.session_state.user = username
                        st.success("Logged in successfully!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")

        with tab2:
            with st.form("signup_form"):
                new_username = st.text_input("New Username")
                new_password = st.text_input("New Password", type="password")
                submit_button = st.form_submit_button("Sign Up")
                if submit_button:
                    if register_user(new_username, new_password):
                        st.success("User registered successfully! Please log in.")
                    else:
                        st.error("Username already exists")

    if st.session_state.user:
        st.write(f"Welcome, {st.session_state.user}!")
        if st.button("Logout"):
            st.session_state.user = None
            st.rerun()

        # Initialize session state
        if 'df' not in st.session_state:
            st.session_state.df = load_tasks()
        if 'editing_task' not in st.session_state:
            st.session_state.editing_task = None

        df = st.session_state.df

        # Task input form
        with st.form(key='task_form'):
            task = st.text_input("Task")
            category = st.selectbox("Category", ["Work", "Personal", "Other"])
            priority = st.selectbox("Priority", ["Low", "Medium", "High"])
            description = st.text_area("Description (optional)", help="Leave blank for AI to generate a description.")
            scheduled_date = st.date_input("Schedule Date (optional)")
            scheduled_time = st.time_input("Schedule Time (optional)")
            
            # AI-Description button
            ai_description_trigger = st.checkbox("Use AI-Description ⭐")

            submitted = st.form_submit_button(label="Add Task")

            if submitted and task:
                if ai_description_trigger and not description:
                    with st.spinner("Generating AI description..."):
                        description = generate_ai_description(task, category, priority)
                    st.success(f"AI Description generated: '{description}'")
                elif not description:
                    description = "No description provided."

                new_task = pd.DataFrame({
                    'User': [st.session_state.user],
                    'Task': [task], 
                    'Category': [category], 
                    'Priority': [priority], 
                    'Completed': [False],
                    'Description': [description],
                    'ScheduledDate': [scheduled_date],
                    'ScheduledTime': [scheduled_time.strftime('%H:%M:%S')]
                })
                st.session_state.df = pd.concat([st.session_state.df, new_task], ignore_index=True)
                save_tasks(st.session_state.df)
                if scheduled_date and scheduled_time:
                    schedule_notification(task, scheduled_date, scheduled_time)
                st.success(f"Task '{task}' added with description!")
                st.rerun()
            elif submitted:
                st.warning("Please enter a task before submitting.")

        # Display tasks
        st.subheader("Tasks")
        user_tasks = st.session_state.df[st.session_state.df['User'] == st.session_state.user]
        if not user_tasks.empty:
            for i, row in user_tasks.iterrows():
                task_text = f"**{row['Task']}** (Category: {row['Category']}, Priority: {row['Priority']})"
                task_description = row['Description']
                scheduled_date = row['ScheduledDate']
                scheduled_time = row['ScheduledTime']
                if row['Completed']:
                    st.write(f"~~{task_text}~~ - {task_description}")
                else:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(task_text)
                        st.text(f"Description: {task_description}")
                        if scheduled_date and scheduled_time:
                            st.text(f"Scheduled for: {scheduled_date} at {scheduled_time}")
                    with col2:
                        if st.button(f"Mark as Done", key=f"done_{i}"):
                            st.session_state.df.at[i, 'Completed'] = True
                            save_tasks(st.session_state.df)
                            st.rerun()
                    with col3:
                        if st.button(f"Edit", key=f"edit_{i}"):
                            st.session_state.editing_task = i
                            st.rerun()

            if st.session_state.editing_task is not None:
                i = st.session_state.editing_task
                with st.form(key=f'edit_form_{i}'):
                    task = st.text_input("Task", value=st.session_state.df.at[i, 'Task'])
                    category = st.selectbox("Category", ["Work", "Personal", "Other"], index=["Work", "Personal", "Other"].index(st.session_state.df.at[i, 'Category']))
                    priority = st.selectbox("Priority", ["Low", "Medium", "High"], index=["Low", "Medium", "High"].index(st.session_state.df.at[i, 'Priority']))
                    description = st.text_area("Description", value=st.session_state.df.at[i, 'Description'])
                    scheduled_date = st.date_input("Schedule Date", value=pd.to_datetime(st.session_state.df.at[i, 'ScheduledDate']).date() if pd.notnull(st.session_state.df.at[i, 'ScheduledDate']) else None)
                    scheduled_time = st.time_input("Schedule Time", value=pd.to_datetime(st.session_state.df.at[i, 'ScheduledTime']).time() if pd.notnull(st.session_state.df.at[i, 'ScheduledTime']) else None)
                    
                    if st.form_submit_button("Update Task"):
                        st.session_state.df.at[i, 'Task'] = task
                        st.session_state.df.at[i, 'Category'] = category
                        st.session_state.df.at[i, 'Priority'] = priority
                        st.session_state.df.at[i, 'Description'] = description
                        st.session_state.df.at[i, 'ScheduledDate'] = scheduled_date
                        st.session_state.df.at[i, 'ScheduledTime'] = scheduled_time.strftime('%H:%M:%S') if scheduled_time else None
                        save_tasks(st.session_state.df)
                        if scheduled_date and scheduled_time:
                            schedule_notification(task, scheduled_date, scheduled_time)
                        st.session_state.editing_task = None
                        st.rerun()

            if st.button("Clear Completed Tasks"):
                st.session_state.df = st.session_state.df[
                    (st.session_state.df['User'] != st.session_state.user) | 
                    (st.session_state.df['Completed'] == False)
                ]
                save_tasks(st.session_state.df)
                st.rerun()
        else:
            st.write("No tasks yet!")

if __name__ == "__main__":
    todo_app()
