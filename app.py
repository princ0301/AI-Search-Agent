import streamlit as st
import sys_msgs
import requests
import trafilatura
from bs4 import BeautifulSoup
from groq import Groq
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Groq client
@st.cache_resource
def get_groq_client():
    # Get API key from environment variable
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("GROQ_API_KEY not found in environment variables. Make sure you have a .env file with this key.")
        st.stop()
    return Groq(api_key=api_key)

# Page configuration
st.set_page_config(
    page_title="AI Web Search Agent",
    page_icon="🔍",
    layout="wide",
)

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = []
if "assistant_convo" not in st.session_state:
    st.session_state.assistant_convo = []
    if hasattr(sys_msgs, 'assistant_msg'):
        st.session_state.assistant_convo = [{"role": "system", "content": str(sys_msgs.assistant_msg)}]
if "model" not in st.session_state:
    st.session_state.model = "llama3-70b-8192"

# Sidebar for configuration
with st.sidebar:
    st.title("AI Web Search Agent")
    st.write("Configuration")
    
    # Model selection
    model_options = ["llama3-70b-8192", "mixtral-8x7b-32768"]
    selected_model = st.selectbox("Select LLM Model", model_options)
    st.session_state.model = selected_model
    
    # Display API status
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        st.success("GROQ_API_KEY loaded successfully")
    else:
        st.error("GROQ_API_KEY not found. Add it to your .env file")
    
    # Show additional info about usage
    st.markdown("---")
    st.write("### How to use:")
    st.write("1. Type your query in the chat input")
    st.write("2. The agent will determine if a web search is needed")
    st.write("3. Results will be displayed in the chat")
    
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.session_state.assistant_convo = []
        if hasattr(sys_msgs, 'assistant_msg'):
            st.session_state.assistant_convo = [{"role": "system", "content": str(sys_msgs.assistant_msg)}]
        st.rerun()

# Main functionality
def search_or_not(user_message):
    sys_msg = str(sys_msgs.search_or_not_msg)
    
    client = get_groq_client()
    completion = client.chat.completions.create(
        model=st.session_state.model,
        messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_message}
        ]
    )
    
    content = completion.choices[0].message.content
    return 'true' in content.lower()

def query_generator(user_message):
    sys_msg = str(sys_msgs.query_msg)
    user_msg = f'CREATE A SEARCH QUERY FOR THIS PROMPT: \n{user_message}'
    
    client = get_groq_client()
    completion = client.chat.completions.create(
        model=st.session_state.model,
        messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg}
        ]
    )
    
    return completion.choices[0].message.content

def duckduckgo_search(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }
    url = f'https://html.duckduckgo.com/html/?q={query}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    results = []
    
    for i, result in enumerate(soup.find_all('div', class_='result'), start=1):
        if i > 10:
            break
            
        title_tag = result.find('a', class_='result__a')
        if not title_tag:
            continue
            
        link = title_tag['href']
        snippet_tag = result.find('a', class_='result__snippet')
        snippet = snippet_tag.text.strip() if snippet_tag else "No description available"
            
        results.append({
            'id': i,   
            'link': link,
            'search_description': snippet
        })
            
    return results

def best_search_result(s_results, query, user_message):
    sys_msg = str(sys_msgs.best_search_msg)
    best_msg = f'SEARCH_RESULTS: {s_results} \nUSER_PROMPT: {user_message} \nSEARCH_QUERY: {query}'
    
    client = get_groq_client()
    for _ in range(2):
        try:
            completion = client.chat.completions.create(
                model=st.session_state.model,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": best_msg}
                ]
            )
            
            return int(completion.choices[0].message.content)
        except:
            continue
        
    return 0

def scrape_webpage(url):
    try:
        downloaded = trafilatura.fetch_url(url=url)
        return trafilatura.extract(downloaded, include_formatting=True, include_links=True)
    except Exception as e:
        return None

def contains_data_needed(search_content, query, user_message):
    sys_msg = str(sys_msgs.contains_data_msg)
    needed_prompt = f'PAGE_TEXT: {search_content} \nUSER_PROMPT: {user_message} \nSEARCH_QUERY: {query}'
    
    client = get_groq_client()
    completion = client.chat.completions.create(
        model=st.session_state.model,
        messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": needed_prompt}
        ]
    )
    
    content = completion.choices[0].message.content
    return 'true' in content.lower()

def ai_search(user_message, search_status_container):
    context = None
    
    with search_status_container:
        st.write("🔍 Generating search query...")
        search_query = query_generator(user_message)
        
        if search_query[0] == '"':
            search_query = search_query[1:-1]
            
        st.write(f"🔍 Searching DuckDuckGo for: '{search_query}'")
        search_results = duckduckgo_search(search_query)
        
        if not search_results:
            st.write("❌ No search results found")
            return None
            
        st.write(f"📊 Found {len(search_results)} search results")
        
        context_found = False
        
        while not context_found and len(search_results) > 0:
            best_result = best_search_result(s_results=search_results, query=search_query, user_message=user_message)
            try:
                page_link = search_results[best_result]['link']
                st.write(f"📄 Checking source: {page_link}")
            except:
                st.write("⚠️ Failed to select best search result, trying again...")
                continue
            
            page_text = scrape_webpage(page_link)
            search_results.pop(best_result)
            
            if page_text and contains_data_needed(search_content=page_text, query=search_query, user_message=user_message):
                context = page_text
                context_found = True
                st.write(f"✅ Data found for query: '{search_query}'")
                st.write(f"Source: {page_link}")
            else:
                st.write("❌ Data not relevant, trying next result...")
    
    return context

def generate_assistant_response(prompt):
    client = get_groq_client()
    messages = [{"role": msg["role"], "content": str(msg["content"])} for msg in st.session_state.assistant_convo]
    
    completion = client.chat.completions.create(
        model=st.session_state.model,
        messages=messages
    )
    
    complete_response = completion.choices[0].message.content
    st.session_state.assistant_convo.append({"role": "assistant", "content": complete_response})
    
    return complete_response

# Main chat UI
st.title("AI Web Search Agent Chat")

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle user input
if prompt := st.chat_input("What would you like to know?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Add user message to assistant conversation
    st.session_state.assistant_convo.append({"role": "user", "content": str(prompt)})
    
    # Check if API key is available
    if not os.getenv("GROQ_API_KEY"):
        with st.chat_message("assistant"):
            st.error("API key not found. Please add GROQ_API_KEY to your .env file.")
    else:
        # Determine if search is needed
        with st.chat_message("assistant"):
            with st.status("Processing your request...") as status:
                should_search = search_or_not(prompt)
                
                if should_search:
                    st.write("Web search is needed for this query.")
                    search_status_container = st.empty()
                    context = ai_search(prompt, search_status_container)
                    
                    # Remove the last user message to prepare for the enhanced prompt
                    st.session_state.assistant_convo = st.session_state.assistant_convo[:-1]
                    
                    if context:
                        enhanced_prompt = f'SEARCH RESULT: {context} \n\nUSER PROMPT: {prompt}'
                    else:
                        enhanced_prompt = (
                            f'USER PROMPT: \n{prompt} \n\nFAILED SEARCH: \nThe '
                            'AI search model was unable to extract any reliable data. Explain that '
                            'and ask if the user would like you to search again or respond '
                            'without web search context.'
                        )
                    
                    st.session_state.assistant_convo.append({"role": "user", "content": str(enhanced_prompt)})
                else:
                    st.write("Using existing knowledge to answer.")
                
                status.update(label="Generating response...", state="running")
                response = generate_assistant_response(prompt)
                st.markdown(response)
                status.update(label="Complete!", state="complete")
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})