import re
import random
import string
import aiohttp
from bs4 import BeautifulSoup

class TelegramOrgScraper:
    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.phone = ""
        self.random_hash = ""

    async def send_code(self, phone: str):
        self.phone = phone
        url = "https://my.telegram.org/auth/send_password"
        data = {"phone": phone}
        async with self.session.post(url, data=data) as resp:
            text = await resp.text()
            try:
                json_data = await resp.json(content_type=None)
                self.random_hash = json_data.get("random_hash")
                return True, "Kod yuborildi."
            except Exception as e:
                return False, f"Xato: {text}"

    async def login_and_get_api(self, code: str):
        # 1. Login
        login_url = "https://my.telegram.org/auth/login"
        login_data = {
            "phone": self.phone,
            "random_hash": self.random_hash,
            "password": code
        }
        async with self.session.post(login_url, data=login_data) as resp:
            text = await resp.text()
            if text != "true":
                return False, f"Kod noto'g'ri yoki xato: {text}"

        # 2. Check Apps page
        apps_url = "https://my.telegram.org/apps"
        async with self.session.get(apps_url) as resp:
            html = await resp.text()

        soup = BeautifulSoup(html, 'html.parser')
        
        # Check if already has api_id
        api_id_span = soup.find('span', string=re.compile(r'^\d+$')) # simplistic approach, better to regex
        
        api_id = None
        api_hash = None
        
        match_id = re.search(r'<strong>App api_id:</strong>.*?<span>(\d+)</span>', html, re.DOTALL | re.IGNORECASE)
        match_hash = re.search(r'<strong>App api_hash:</strong>.*?<span>([a-f0-9]+)</span>', html, re.DOTALL | re.IGNORECASE)
        
        if match_id and match_hash:
            api_id = match_id.group(1)
            api_hash = match_hash.group(1)
            return True, {"api_id": int(api_id), "api_hash": api_hash}
        
        # 3. Create app if not exists
        hash_input = soup.find('input', {'name': 'hash'})
        if not hash_input:
            return False, "Hash topilmadi, akkaunt limitga tushgan bo'lishi mumkin."
            
        form_hash = hash_input.get('value')
        
        create_url = "https://my.telegram.org/apps/create"
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        create_data = {
            "hash": form_hash,
            "app_title": "Smm Agent AI",
            "app_shortname": f"smmagentai{random_suffix}",
            "app_url": "",
            "app_platform": "android",
            "app_desc": "Automated SMM Agent"
        }
        
        async with self.session.post(create_url, data=create_data) as resp:
            # After creation, it usually redirects to /apps
            pass
            
        # 4. Fetch again
        async with self.session.get(apps_url) as resp:
            html = await resp.text()
            
        match_id = re.search(r'<strong>App api_id:</strong>.*?<span>(\d+)</span>', html, re.DOTALL | re.IGNORECASE)
        match_hash = re.search(r'<strong>App api_hash:</strong>.*?<span>([a-f0-9]+)</span>', html, re.DOTALL | re.IGNORECASE)
        
        if match_id and match_hash:
            api_id = match_id.group(1)
            api_hash = match_hash.group(1)
            return True, {"api_id": int(api_id), "api_hash": api_hash}
            
        with open('failed_html.html', 'w', encoding='utf-8') as errf:
            errf.write(html)
        return False, "API ID va HASH yaratib bo'lmadi. (HTML saqlandi)"

    async def close(self):
        await self.session.close()

