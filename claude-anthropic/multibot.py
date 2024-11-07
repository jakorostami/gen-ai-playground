import os
from anthropic import Anthropic
import google.generativeai as genai
from config import IDENTITY, TOOLS, MODEL, get_quote
from dotenv import load_dotenv



load_dotenv()

class MultiChatBot:
    def __init__(self, session_state):
        # Initialize both AI clients
        self.anthropic = Anthropic()
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        # Initialize chat sessions
        self.session_state = session_state
        self.gemini_chat = self.gemini_model.start_chat(history=[])
        
        # Initialize conversation history for both AIs
        if not hasattr(self.session_state, 'messages'):
            self.session_state.messages = []
        if not hasattr(self.session_state, 'gemini_history'):
            self.session_state.gemini_history = []

    def generate_claude_message(self, messages, max_tokens):
        try:
            response = self.anthropic.messages.create(
                model=MODEL,
                system=IDENTITY,
                max_tokens=max_tokens,
                messages=messages,
                tools=TOOLS,
            )
            return response
        except Exception as e:
            return {"error": str(e)}

    def generate_gemini_message(self, message):
        try:
            response = self.gemini_chat.send_message(message)
            return response.text
        except Exception as e:
            return f"Gemini Error: {str(e)}"

    def process_conversation(self, user_input, target_ai="both"):
        """
        Process conversation with specified AI(s)
        target_ai options: "claude", "gemini", "both"
        """
        responses = []
        
        if target_ai in ["claude", "both"]:
            # Get Claudes response
            self.session_state.messages.append({"role": "user", "content": user_input})
            claude_response = self.generate_claude_message(
                messages=self.session_state.messages,
                max_tokens=2048,
            )
            
            if "error" in claude_response:
                responses.append(f"Claude: Error - {claude_response['error']}")
            else:
                claude_text = claude_response.content[0].text
                responses.append(f"Claude: {claude_text}")
                self.session_state.messages.append(
                    {"role": "assistant", "content": claude_text}
                )

        if target_ai in ["gemini", "both"]:
            try:
                # Get Geminis response
                gemini_response = self.generate_gemini_message(user_input)
                responses.append(f"Gemini: {gemini_response}")
                self.session_state.gemini_history.append({
                    "role": "user",
                    "content": user_input
                })
                self.session_state.gemini_history.append({
                    "role": "assistant",
                    "content": gemini_response
                })
            except Exception as e:
                responses.append(f"Gemini: Error - {str(e)}")

        # For single AI responses, return without the prefix
        if target_ai == "claude":
            return responses[0] if responses else "Claude: No response"
        elif target_ai == "gemini":
            return responses[0] if responses else "Gemini: No response"
        
        # Join responses with newlines if there are multiple
        return "\n".join(responses) if responses else "No response received"

    def ai_dialogue(self, topic, turns=3):
        """
        Generate a dialogue between Claude and Gemini on a specific topic with consistent formatting
        """
        # Start with the topic header
        dialogue_parts = [f"Starting AI dialogue on topic: {topic}\n"]
        previous_message = topic
        
        for i in range(turns):
            # Claudes turn
            claude_prompt = (f"Respond to this message in the dialogue about '{topic}': "
                            f"'{previous_message}'. Be concise and engaging.")
            
            claude_response = self.process_conversation(claude_prompt, "claude")
            claude_text = claude_response.replace("Claude: ", "")
            dialogue_parts.append(f"Claude: {claude_text}")
            
            # Use Claudes response as input for Gemini
            gemini_prompt = (f"You are in a dialogue about '{topic}'. "
                            f"Respond to Claude's message: '{claude_text}'. "
                            f"Be concise and engaging.")
            
            gemini_response = self.process_conversation(gemini_prompt, "gemini")
            gemini_text = gemini_response.replace("Gemini: ", "")
            dialogue_parts.append(f"Gemini: {gemini_text}\n")
            
            # Update previous message for next turn
            previous_message = gemini_text
        
        # Join all parts with consistent formatting
        return "\n".join(dialogue_parts)

    def handle_tool_use(self, func_name, func_params):
        if func_name == "get_quote":
            premium = get_quote(**func_params)
            return f"Quote generated: ${premium:.2f} per month"
        raise Exception("An unexpected tool was used")