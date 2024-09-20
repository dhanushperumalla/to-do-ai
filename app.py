import streamlit as st
import pandas as pd
import os
from datetime import date
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate

# Initialize the Groq model
groq_api_key = st.secrets["GROQ_API_KEY"]
model = ChatGroq(model="Gemma2-9b-It", groq_api_key=groq_api_key)

# File to store tasks
TASKS_FILE = "tasks.csv"

# Initialize the tasks file if it doesn't exist
if not os.path.exists(TASKS_FILE):
    df = pd.DataFrame(columns=['Task', 'Category', 'Priority', 'Completed', 'Description', 'Deadline'])
    df.to_csv(TASKS_FILE, index=False)

# Load tasks from the CSV file
def load_tasks():
    return pd.read_csv(TASKS_FILE)

# Save tasks to the CSV file
def save_tasks(df):
    df.to_csv(TASKS_FILE, index=False)

# Prompt template for AI description
description_template = PromptTemplate(
    input_variables=["task", "category", "priority"],
    template="""Generate a brief, motivating description for the following task:
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

# UI for the app
def todo_app():
    st.title("AI-based To-Do List with Task Descriptions and Deadlines")

    # Initialize session state
    if 'df' not in st.session_state:
        st.session_state.df = load_tasks()
    if 'editing_task' not in st.session_state:
        st.session_state.editing_task = None

    df = st.session_state.df

    # Task input form
    with st.form(key='task_form', clear_on_submit=True):
        task = st.text_input("Task")
        category = st.selectbox("Category", ["Work", "Personal", "Other"])
        priority = st.selectbox("Priority", ["Low", "Medium", "High"])
        description = st.text_area("Description (optional)", help="Leave blank for AI to generate a description.")
        deadline = st.date_input("Deadline", value=date.today(), help="Select the deadline for this task.")
        
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
                'Task': [task], 
                'Category': [category], 
                'Priority': [priority], 
                'Completed': [False],
                'Description': [description],
                'Deadline': [deadline]  # Add the deadline here
            })
            st.session_state.df = pd.concat([st.session_state.df, new_task], ignore_index=True)
            save_tasks(st.session_state.df)
            st.success(f"Task '{task}' added with deadline {deadline}!")
            st.rerun()
        elif submitted:
            st.warning("Please enter a task before submitting.")

    # Display tasks
    st.subheader("Tasks")
    if not st.session_state.df.empty:
        for i, row in st.session_state.df.iterrows():
            task_text = f"**{row['Task']}** (Category: {row['Category']}, Priority: {row['Priority']}, Deadline: {row['Deadline']})"
            task_description = row['Description']
            if row['Completed']:
                st.write(f"~~{task_text}~~ - {task_description}")
            else:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(task_text)
                    st.text(f"Description: {task_description}")
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
                deadline = st.date_input("Deadline", value=pd.to_datetime(st.session_state.df.at[i, 'Deadline']).date())
                
                if st.form_submit_button("Update Task"):
                    st.session_state.df.at[i, 'Task'] = task
                    st.session_state.df.at[i, 'Category'] = category
                    st.session_state.df.at[i, 'Priority'] = priority
                    st.session_state.df.at[i, 'Description'] = description
                    st.session_state.df.at[i, 'Deadline'] = deadline
                    save_tasks(st.session_state.df)
                    st.session_state.editing_task = None
                    st.rerun()

        if st.button("Clear Completed Tasks"):
            st.session_state.df = st.session_state.df[st.session_state.df['Completed'] == False]
            save_tasks(st.session_state.df)
            st.rerun()
    else:
        st.write("No tasks yet!")

if __name__ == "__main__":
    todo_app()
