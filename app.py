import streamlit as st
import httpx
import asyncio
import os
from apify_client import ApifyClient

# --- КОНФИГУРАЦИЯ ---
st.set_page_config(page_title="RH Studio Pro", layout="wide", page_icon="⚡")

# Ключи из твоего бота
RH_API_KEY = "781fe4abc655454b81ffa8855e4b0849"
APIFY_TOKEN = "apify_api_ZZn2PnXNgzW9AYlNOUlxg75A4te7C82JT5Cn"
SCRAPER_ID = "clockworks/tiktok-scraper"
APP_ID_V1 = "2044885484895211521"
APP_ID_V2 = "2044904461180608513"
RH_BASE_URL = "https://www.runninghub.ai/openapi/v2"
RH_UPLOAD_URL = "https://www.runninghub.cn/openapi/v2/media/upload/binary"

apify_client = ApifyClient(APIFY_TOKEN)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def find_key_recursive(obj, key):
    if isinstance(obj, dict):
        if key in obj: return obj[key]
        for v in obj.values():
            res = find_key_recursive(v, key)
            if res: return res
    elif isinstance(obj, list):
        for i in obj:
            res = find_key_recursive(i, key)
            if res: return res
    return None

def find_media_urls_recursive(obj, out_list):
    if isinstance(obj, str):
        val = obj.strip()
        if val.startswith("http") and any(x in val.lower() for x in [".mp4", ".jpg", ".png", "output"]):
            if val not in out_list: out_list.append(val)
    elif isinstance(obj, dict):
        for v in obj.values(): find_media_urls_recursive(v, out_list)
    elif isinstance(obj, list):
        for i in obj: find_media_urls_recursive(i, out_list)

async def upload_to_rh(file_bytes, file_name):
    headers = {"Authorization": f"Bearer {RH_API_KEY}"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        files = {'file': (file_name, file_bytes)}
        response = await client.post(RH_UPLOAD_URL, headers=headers, files=files)
        return find_key_recursive(response.json(), "download_url")

async def run_and_wait_st(app_id, nodes):
    headers = {"Authorization": f"Bearer {RH_API_KEY}", "Content-Type": "application/json"}
    payload = {"nodeInfoList": nodes, "instanceType": "default"}
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(f"{RH_BASE_URL}/run/ai-app/{app_id}", json=payload, headers=headers)
        task_id = find_key_recursive(resp.json(), "taskId")
        if not task_id: return None, f"Ошибка запуска: {resp.text}"
        
        status_placeholder = st.empty()
        while True:
            await asyncio.sleep(8)
            st_res = await client.post(f"{RH_BASE_URL}/query", json={"taskId": task_id}, headers=headers)
            status_data = st_res.json()
            status = find_key_recursive(status_data, "status")
            status_placeholder.info(f"⏳ Статус: {status} (Task: {task_id})")
            if status == "SUCCESS": return status_data, None
            if status in ["FAILED", "CANCELLED"]: return None, f"Workflow {status}"

async def get_tiktok_mp4(url):
    """Метод из bot.py для получения прямой ссылки"""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            res = await client.get(f"https://www.tikwm.com/api/?url={url}")
            data = res.json().get("data")
            if data:
                play = data.get("play")
                return play if play.startswith("http") else "https://www.tikwm.com" + play
    except: return None

# --- ИНТЕРФЕЙС ---
tab1, tab2, tab3 = st.tabs(["🎭 V1: DeepFake", "⚡ V2: Universal", "📱 TikTok References"])

with tab1:
    st.header("Воркфлоу V1 (Замена лица)")
    c1, c2 = st.columns(2)
    with c1: v1_vid = st.file_uploader("Видео", type=['mp4','mov'], key="uv1")
    with c2: v1_img = st.file_uploader("Лицо", type=['jpg','png'], key="ui1")
    v1_sec = st.number_input("Длина (сек)", value=5, min_value=1)
    if st.button("Запустить V1", use_container_width=True):
        if v1_vid and v1_img:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            with st.spinner("Генерация..."):
                uv = loop.run_until_complete(upload_to_rh(v1_vid.getvalue(), v1_vid.name))
                uf = loop.run_until_complete(upload_to_rh(v1_img.getvalue(), v1_img.name))
                nodes = [
                    {"nodeId": "52", "fieldName": "video", "fieldValue": str(uv)},
                    {"nodeId": "167", "fieldName": "image", "fieldValue": str(uf)},
                    {"nodeId": "439", "fieldName": "value", "fieldValue": str(int(v1_sec)+2)} # Логика из bot.py
                ]
                res, err = loop.run_until_complete(run_and_wait_st(APP_ID_V1, nodes))
                if err: st.error(err)
                else:
                    urls = []
                    find_media_urls_recursive(res, urls)
                    for u in urls:
                        if ".mp4" in u.lower(): st.video(u)
                        else: st.image(u)
        else: st.warning("Загрузите файлы!")

with tab2:
    st.header("Воркфлоу V2")
    v2_mode = st.radio("Тип:", ["Видео", "Фото"], horizontal=True)
    v2_file = st.file_uploader(f"Файл {v2_mode}", type=['mp4','mov','jpg','png'], key="uv2")
    if st.button("Запустить V2", use_container_width=True):
        if v2_file:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            with st.spinner("Обработка..."):
                url = loop.run_until_complete(upload_to_rh(v2_file.getvalue(), v2_file.name))
                if v2_mode == "Фото":
                    nodes = [{"nodeId":"529","fieldName":"value","fieldValue":"2"},{"nodeId":"528","fieldName":"image","fieldValue":str(url)}]
                else:
                    nodes = [{"nodeId":"529","fieldName":"value","fieldValue":"1"},{"nodeId":"517","fieldName":"video","fieldValue":str(url)}]
                res, err = loop.run_until_complete(run_and_wait_st(APP_ID_V2, nodes))
                if err: st.error(err)
                else:
                    urls = []
                    find_media_urls_recursive(res, urls)
                    for u in urls:
                        if ".mp4" in u.lower(): st.video(u)
                        else: st.image(u)

with tab3:
    st.header("📱 Все найденные референсы")
    if st.button("🔄 Загрузить всё из Apify", use_container_width=True):
        with st.spinner("Получение данных..."):
            runs = apify_client.actor(SCRAPER_ID).runs().list(limit=1, desc=True)
            if runs.items:
                items = apify_client.dataset(runs.items[0]['defaultDatasetId']).list_items().items
                st.success(f"Найдено видео: {len(items)}")
                
                # Сетка 3 колонки
                cols = st.columns(3)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                for i, item in enumerate(items):
                    orig_link = item.get('webVideoUrl') or item.get('videoUrl') or item.get('url')
                    with cols[i % 3]:
                        with st.container(border=True):
                            st.write(f"**🎥 Видео #{i+1}**")
                            # Сначала пробуем TikWM
                            direct = loop.run_until_complete(get_tiktok_mp4(orig_link))
                            if direct:
                                st.video(direct)
                            else:
                                # Если TikWM подвел, пробуем ссылку из Apify напрямую
                                fallback = item.get('videoUrl')
                                if fallback: st.video(fallback)
                                else: st.info("Плеер заблокирован TikTok")
                            
                            st.write(f"🔗 [Оригинал в TikTok]({orig_link})")
            else:
                st.error("Данные скрапера не найдены.")