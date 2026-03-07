import pandas as pd
import os
import json
from dotenv import load_dotenv
from ddgs import DDGS
from tavily import TavilyClient
from openai import OpenAI
from tqdm import tqdm

load_dotenv()

class Converter:
    def __init__(self):
        self.ddg = DDGS()
        tavily_key = os.getenv('TAVILY_API_KEY')
        self.tavily = TavilyClient(api_key=tavily_key) if tavily_key else None
        openrouter_key = os.getenv('OPENROUTER_API_KEY')
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key
        ) if openrouter_key else None
        self.country_to_lang = {
            'bulgaria': 'bg',
            'media': 'bg',
            'europe': 'en',
            'germany': 'de',
            'estonia': 'et',
            'france': 'fr',
            'italy': 'it',
            'spain': 'es',
            # Add more as needed
        }

    def clean_name(self, raw_name):
        prefixes = ['MEP ', 'Mr. ', 'Mrs. ', 'Ms. ', 'High Representative ']
        for prefix in prefixes:
            raw_name = raw_name.replace(prefix, '')
        return raw_name.strip().title()

    def search_snippet(self, name, group):
        query = f'"{name}" politician OR MEP OR MP {group} country OR nationality OR language OR party'
        try:
            ddg_results = self.ddg.text(query, max_results=5, region='wt')
            snippet = '\n'.join([r['body'] for r in ddg_results if r['body']])
        except Exception:
            snippet = ''
        if not snippet and self.tavily:
            try:
                tavily_results = self.tavily.search(query, max_results=5, search_depth='basic')
                snippet = '\n'.join([r['content'] for r in tavily_results['results'] if r.get('content')])
            except Exception:
                snippet = ''
        return snippet

    def extract_with_ai(self, raw_name, group, snippet):
        if not self.client:
            # Fallback without AI
            name = self.clean_name(raw_name)
            info = group
            lang = self.country_to_lang.get(group.lower(), 'en')
            return {'name': name, 'email': '', 'info': info, 'language': lang}

        prompt = f"""Extract structured info for political email personalization. Output ONLY valid JSON.

Raw name: "{raw_name}"
Group/Context: {group}
Search snippet: {snippet[:3000]}

Infer:
- name: Clean full name (title case, remove MEP/Mr./etc.)
- info: Position/party/group (e.g. "MEP EPP", "Foreign Minister")
- language: 2-letter ISO code (bg, de, en, fr, etc.) based on country/nationality

{{"name": "Radan Kanev", "info": "MEP EPP", "language": "bg"}}"""
        try:
            response = self.client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            content = response.choices[0].message.content.strip()
            extracted = json.loads(content)
            return extracted
        except Exception:
            # Fallback
            pass

        name = self.clean_name(raw_name)
        info = group
        lang = self.country_to_lang.get(group.lower(), 'en')
        return {'name': name, 'info': info, 'language': lang}

    def convert(self, input_path, output_path):
        if not os.path.exists(input_path):
            print(f"Error: {input_path} not found.")
            return
        df = pd.read_csv(input_path)
        print(f"Processing {len(df)} rows...")
        results = []
        for _, row in tqdm(df.iterrows(), total=len(df), desc="Converting"):
            email = row['Emails'].strip()
            raw_name = row['Names']
            group = row['Group']
            snippet = self.search_snippet(raw_name, group)
            extracted = self.extract_with_ai(raw_name, group, snippet)
            extracted['email'] = email
            # Ensure order
            row_data = {
                'name': extracted.get('name', raw_name),
                'email': email,
                'info': extracted.get('info', group),
                'language': extracted.get('language', 'en')
            }
            results.append(row_data)
        output_df = pd.DataFrame(results)
        output_df.to_csv(output_path, index=False, encoding='utf-8')
        print(f"✅ Converted {len(results)} rows to {output_path}")

if __name__ == '__main__':
    conv = Converter()
    input_file = 'Contacting Emails [EU] - Sheet1.csv'
    output_file = 'sample_draft.csv'
    conv.convert(input_file, output_file)
    print("Conversion complete! Check sample_draft.csv")