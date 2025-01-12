import sys_msgs
import requests
import trafilatura
from bs4 import BeautifulSoup
from colorama import init, Fore, Style
from groq import Groq

init(autoreset=True)
# Initialize Groq client
client = Groq(
    api_key="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",  # Replace with your Groq API key
)

# Using Groq's LLM-2 model
MODEL = "llama3-70b-8192"

# Initialize conversation with system message
assistant_convo = []
if hasattr(sys_msgs, 'assistant_msg'):
    assistant_convo = [{"role": "system", "content": str(sys_msgs.assistant_msg)}]

def search_or_not():
    sys_msg = str(sys_msgs.search_or_not_msg)
    user_msg = str(assistant_convo[-1]["content"]) if assistant_convo else ""
    
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg}
        ]
    )
    
    content = completion.choices[0].message.content
    return 'true' in content.lower()

def query_generator():
    sys_msg = str(sys_msgs.query_msg)
    user_msg = f'CREATE A SEARCH QUERY FOR THIS PROMPT: \n{str(assistant_convo[-1]["content"])}'
    
    completion = client.chat.completions.create(
        model=MODEL,
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

def best_search_result(s_results, query):
    sys_msg = str(sys_msgs.best_search_msg)
    best_msg = f'SEARCH_RESULTS: {s_results} \nUSER_PROMPT: {str(assistant_convo[-1]["content"])} \nSEARCH_QUERY: {query}'
    
    for _ in range(2):
        try:
            completion = client.chat.completions.create(
                model=MODEL,
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

def contains_data_needed(search_content, query):
    sys_msg = str(sys_msgs.contains_data_msg)
    needed_prompt = f'PAGE_TEXT: {search_content} \nUSER_PROMPT: {str(assistant_convo[-1]["content"])} \nSEARCH_QUERY: {query}'
    
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": needed_prompt}
        ]
    )
    
    content = completion.choices[0].message.content
    return 'true' in content.lower()

def ai_search():
    context = None
    print(f'{Fore.YELLOW}GENERATING SEARCH QUERY.{Style.RESET_ALL}')
    search_query = query_generator()
    print(f'{Fore.YELLOW}SEARCHING DuckDuckGo FOR: {search_query}{Style.RESET_ALL}')
    
    if search_query[0] == '"':
        search_query = search_query[1:-1]
        
    search_results = duckduckgo_search(search_query)
    context_found = False
    
    while not context_found and len(search_results) > 0:
        best_result = best_search_result(s_results=search_results, query=search_query)
        try:
            page_link = search_results[best_result]['link']
            # Print clickable link with content source
            print(f'{Fore.CYAN}Content source: \033[4m{page_link}\033[0m{Style.RESET_ALL}')
        except:
            print(f'{Fore.YELLOW}FAILED TO SELECT BEST SEARCH RESULT, TRYING AGAIN.{Style.RESET_ALL}')
            continue
        
        page_text = scrape_webpage(page_link)
        print(f'{Fore.YELLOW}Found {len(search_results)} SEARCH RESULTS.{Style.RESET_ALL}')
        search_results.pop(best_result)
        
        if page_text and contains_data_needed(search_content=page_text, query=search_query):
            context = page_text
            context_found = True
            print(f'{Fore.GREEN}DATA FOUND FOR QUERY: {search_query}{Style.RESET_ALL}')
        else:
            print(f'{Fore.RED}DATA NOT RELEVANT.{Style.RESET_ALL}')
            
    return context

def stream_assistant_response():
    global assistant_convo
    
    # Convert messages to the format expected by Groq
    messages = [{"role": msg["role"], "content": str(msg["content"])} for msg in assistant_convo]
    
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            stream=True
        )
        
        complete_response = ''
        print(f'{Fore.CYAN}ASSISTANT:{Style.RESET_ALL}')
        
        for chunk in completion:
            chunk_content = chunk.choices[0].delta.content
            if chunk_content:
                print(chunk_content, end='', flush=True)
                complete_response += chunk_content
            
        assistant_convo.append({"role": "assistant", "content": complete_response})
        print('\n\n')
    except Exception as e:
        print(f'{Fore.RED}Error in generating response: {str(e)}{Style.RESET_ALL}')

def main():
    global assistant_convo
    
    print(f'{Fore.CYAN}Chat initialized. Type your messages (Ctrl+C to exit){Style.RESET_ALL}\n')
    
    while True:
        try:
            prompt = input(f'{Fore.GREEN}USER: \n{Style.RESET_ALL}')
            if not prompt.strip():
                continue
                
            assistant_convo.append({"role": "user", "content": str(prompt)})
            
            if search_or_not():
                context = ai_search()
                assistant_convo = assistant_convo[:-1]
                
                if context:
                    prompt = f'SEARCH RESULT: {context} \n\nUSER PROMPT: {prompt}'
                else:
                    prompt = (
                        f'USER PROMPT: \n{prompt} \n\nFAILED SEARCH: \nThe '
                        'AI search model was unable to extract any reliable data. Explain that '
                        'and ask if the user would like you to search again or respond '
                        'without web search context.'
                    )
                    
                assistant_convo.append({"role": "user", "content": str(prompt)})
                
            stream_assistant_response()
            
        except KeyboardInterrupt:
            print(f'\n{Fore.YELLOW}Exiting chat...{Style.RESET_ALL}')
            break
        except Exception as e:
            print(f'{Fore.RED}An error occurred: {str(e)}{Style.RESET_ALL}')
            continue

if __name__ == '__main__':
    main()