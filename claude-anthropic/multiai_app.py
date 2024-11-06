import streamlit as st
from multibot import MultiChatBot
from config import TASK_SPECIFIC_INSTRUCTIONS

def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {'role': "user", "content": TASK_SPECIFIC_INSTRUCTIONS},
            {'role': "assistant", "content": "Understood"},
        ]
    if "chat_mode" not in st.session_state:
        st.session_state.chat_mode = "both"
    if "gemini_history" not in st.session_state:
        st.session_state.gemini_history = []
    if "show_ai_dialogue" not in st.session_state:
        st.session_state.show_ai_dialogue = False

def format_response(response, chat_mode):
    """Helper function to format AI responses"""
    if chat_mode == "both":
        # Split responses more safely
        responses = response.split("\n")
        claude_resp = next((r for r in responses if r.startswith("Claude:")), "Claude: No response")
        gemini_resp = next((r for r in responses if r.startswith("Gemini:")), "Gemini: No response")
        
        return f"""
        🔵 **Claude**: {claude_resp.replace('Claude: ', '')}
        
        🟢 **Gemini**: {gemini_resp.replace('Gemini: ', '')}
        """
    else:
        return response

def main():
    st.title("Multi-AI Chat System 🤖")
    
    # Initialize session state
    initialize_session_state()
    
    # Create sidebar for settings
    with st.sidebar:
        st.header("Chat Settings")
        chat_mode = st.radio(
            "Choose who to chat with:",
            ["Both AIs", "Claude Only", "Gemini Only"],
            key="chat_mode_radio"
        )
        
        # Map radio options to internal mode strings
        mode_mapping = {
            "Both AIs": "both",
            "Claude Only": "claude",
            "Gemini Only": "gemini"
        }
        st.session_state.chat_mode = mode_mapping[chat_mode]
        
        if st.button("Start AI-to-AI Dialogue"):
            st.session_state.show_ai_dialogue = True
            
        if st.button("Clear Chat History"):
            st.session_state.messages = [
                {'role': "user", "content": TASK_SPECIFIC_INSTRUCTIONS},
                {'role': "assistant", "content": "Understood"},
            ]
            st.session_state.gemini_history = []
            st.rerun()

    # Initialize chat system
    chat_system = MultiChatBot(st.session_state)

    # Display chat messages
    for message in st.session_state.messages[2:]:
        if isinstance(message["content"], str):
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Handle AI-to-AI dialogue
    if st.session_state.show_ai_dialogue:
        st.subheader("AI-to-AI Dialogue")
        topic = st.text_input("Enter a topic for the AIs to discuss:")
        num_turns = st.slider("Number of dialogue turns:", 1, 5, 3)
        
        if st.button("Generate Dialogue"):
            with st.spinner("Generating AI dialogue..."):
                dialogue = chat_system.ai_dialogue(topic, turns=num_turns)
                # Split the dialogue into lines and format each one
                dialogue_lines = dialogue.split('\n')
                for line in dialogue_lines:
                    if line.strip():  # Skip empty lines
                        if line.startswith('Claude:'):
                            st.markdown(f"🔵 {line}")
                        elif line.startswith('Gemini:'):
                            st.markdown(f"🟢 {line}")
                        else:
                            st.markdown(line)
                st.session_state.show_ai_dialogue = False
    
    # Handle user input
    if user_msg := st.chat_input("Type your message here..."):
        st.chat_message("user").markdown(user_msg)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response_placeholder = st.empty()
                
                # Process message based on selected mode
                response = chat_system.process_conversation(
                    user_msg, 
                    target_ai=st.session_state.chat_mode
                )
                
                # Format and display response
                formatted_response = format_response(response, st.session_state.chat_mode)
                response_placeholder.markdown(formatted_response)

if __name__ == "__main__":
    main()