import pandas as pd
import re
from typing import List, Dict, Tuple
import aiofiles

async def validate_and_parse_csv(file_path: str) -> Tuple[bool, str, List[Dict]]:
    """
    Validate CSV file: required columns, valid emails, max 300 rows.
    Returns (valid: bool, message: str, records: list[dict])
    """
    try:
        # Read CSV with aiofiles + pandas
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        from io import StringIO
        df = pd.read_csv(StringIO(content))
        
        required_cols = ['name', 'email', 'info']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            return False, f"ستون‌های الزامی موجود نیست: {', '.join(missing)}", []
        
        if len(df) > 300:
            return False, "تعداد ردیف‌ها بیش از 300 است", []
        
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        invalid_emails = df[~df['email'].str.match(email_regex, na=False)]['email'].tolist()
        if invalid_emails:
            return False, f"ایمیل‌های نامعتبر: {invalid_emails[:5]}...", []
        
        # Normalize language: any 2-letter code, default 'en'
        df['language'] = df.get('language', pd.Series(['en'] * len(df))).fillna('en').astype(str).str.strip().str.lower().str[:2]
        
        records = df[['name', 'email', 'info', 'language']].to_dict('records')
        return True, "✅ فایل CSV معتبر است", records
        
    except Exception as e:
        return False, f"خطا در خواندن CSV: {str(e)}", []