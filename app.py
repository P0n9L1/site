import streamlit as st
import httpx
import asyncio
import os
from apify_client import ApifyClient

# --- КОНФИГУРАЦИЯ ---
st.set_page_config(page_title="RH Studio Pro", layout="wide", page_icon="⚡")

# Берем ключи из Secrets (безопасный метод)
RH_API_KEY = st.secrets.get("RH_API_KEY", "781fe4abc655454b81ffa8855e4b0849")
APIFY_TOKEN = st.secrets.get("APIFY_TOKEN", "apify_api_ZZn2PnXNgzW9AYlNOUlxg75A4te7C82JT5Cn")

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

async def check_task_status(task_id):
    headers = {"Authorization": f"Bearer {RH_API_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{RH_BASE_URL}/query", json={"taskId": task_id}, headers=headers)
            return resp.json()
        except:
            return None

async def get_tiktok_mp4(url):
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            res = await client.get(f"https://www.tikwm.com/api/?url={url}")
            data = res.json().get("data")
            if data: return data.get("play")
    except: return None

# --- ЛОГИКА ВОССТАНОВЛЕНИЯ СЕССИИ ---
query_params = st.query_params
active_task = query_params.get("task")

# --- ИНТЕРФЕЙС ---
tab1, tab2, tab3 = st.tabs(["🎭 V1: DeepFake", "⚡ V2: Universal", "📱 TikTok Refs"])

# Сайдбар для управления активной задачей
if active_task:
    st.sidebar.info(f"🔍 Отслеживаю задачу: {active_task}")
    if st.sidebar.button("❌ Сбросить задачу"):
        st.query_params.clear()
        st.rerun()

with tab1:
    st.header("Воркфлоу V1 (Face Swap)")
    
    if active_task:
        if st.button("🔄 Проверить готовность", key="check_v1"):
            with st.spinner("Синхронизация с RunningHub..."):
                loop = asyncio.new_event_loop()
                res = loop.run_until_complete(check_task_status(active_task))
                status = find_key_recursive(res, "status")
                if status == "SUCCESS":
                    st.success("Готово!")
                    urls = []
                    find_media_urls_recursive(res, urls)
                    for u in urls: 
                        if ".mp4" in u.lower(): st.video(u)
                        else: st.image(u)
                else:
                    st.info(f"Статус: {status}. Попробуйте позже.")
        st.divider()

    c1, c2 = st.columns(2)
    with c1: v1_vid = st.file_uploader("Видео-основа", type=['mp4','mov'], key="uv1")
    with c2: v1_img = st.file_uploader("Новое лицо", type=['jpg','png'], key="ui1")
    v1_sec = st.number_input("Длительность (сек)", value=5, min_value=1)
    
    if st.button("🚀 Запустить V1", use_container_width=True):
        if v1_vid and v1_img:
            with st.spinner("Загрузка медиа..."):
                loop = asyncio.new_event_loop()
                uv = loop.run_until_complete(upload_to_rh(v1_vid.getvalue(), v1_vid.name))
                uf = loop.run_until_complete(upload_to_rh(v1_img.getvalue(), v1_img.name))
                nodes = [
                    {"nodeId": "52", "fieldName": "video", "fieldValue": str(uv)},
                    {"nodeId": "167", "fieldName": "image", "fieldValue": str(uf)},
                    {"nodeId": "439", "fieldName": "value", "fieldValue": str(int(v1_sec)+2)}
                ]
                headers = {"Authorization": f"Bearer {RH_API_KEY}", "Content-Type": "application/json"}
                resp = httpx.post(f"{RH_BASE_URL}/run/ai-app/{APP_ID_V1}", json={"nodeInfoList": nodes}, headers=headers)
                task_id = find_key_recursive(resp.json(), "taskId")
                
                if task_id:
                    st.query_params.task = task_id
                    st.success(f"Запущено! ID: {task_id}")
                    st.rerun()
                else: st.error("Ошибка API RunningHub")
        else: st.warning("Загрузите файлы!")

with tab2:
    st.header("Воркфлоу V2 (Universal)")
    if active_task:
        if st.button("🔍 Проверить статус V2", key="check_v2"):
            loop = asyncio.new_event_loop()
            res = loop.run_until_complete(check_task_status(active_task))
            status = find_key_recursive(res, "status")
            if status == "SUCCESS":
                urls = []
                find_media_urls_recursive(res, urls)
                for u in urls: st.video(u) if ".mp4" in u.lower() else st.image(u)
            else: st.info(f"Статус: {status}")
        st.divider()

    v2_mode = st.radio("Режим:", ["Видео", "Фото"], horizontal=True)
    v2_file = st.file_uploader(f"Выберите файл", type=['mp4','mov','jpg','png'], key="uv2")
    if st.button("🚀 Запустить V2", use_container_width=True):
        if v2_file:
            with st.spinner("Запуск воркфлоу..."):
                loop = asyncio.new_event_loop()
                url = loop.run_until_complete(upload_to_rh(v2_file.getvalue(), v2_file.name))
                if v2_mode == "Фото":
                    nodes = [{"nodeId":"529","fieldName":"value","fieldValue":"2"},{"nodeId":"528","fieldName":"image","fieldValue":str(url)}]
                else:
                    nodes = [{"nodeId":"529","fieldName":"value","fieldValue":"1"},{"nodeId":"517","fieldName":"video","fieldValue":str(url)}]
                headers = {"Authorization": f"Bearer {RH_API_KEY}", "Content-Type": "application/json"}
                resp = httpx.post(f"{RH_BASE_URL}/run/ai-app/{APP_ID_V2}", json={"nodeInfoList": nodes}, headers=headers)
                task_id = find_key_recursive(resp.json(), "taskId")
                if task_id:
                    st.query_params.task = task_id
                    st.rerun()

with tab3:
    st.header("📱 TikTok References (No Watermark)")
    if st.button("🔄 Обновить ленту референсов", use_container_width=True):
        with st.spinner("Загрузка из Apify..."):
            try:
                runs = apify_client.actor(SCRAPER_ID).runs().list(limit=1, desc=True)
                if runs.items:
                    items = apify_client.dataset(runs.items[0]['defaultDatasetId']).list_items().items
                    if items:
                        cols = st.columns(2)
                        loop = asyncio.new_event_loop()
                        for i, item in enumerate(items):
                            orig = item.get('webVideoUrl') or item.get('url')
                            with cols[i % 2]:
                                with st.container(border=True):
                                    direct = loop.run_until_complete(get_tiktok_mp4(orig))
                                    if direct:
                                        st.video(direct)
                                        # Используем st.html вместо st.markdown для кнопок
                                        st.html(f'''
                                            <a href="{direct}" target="_blank" style="text-decoration:none;">
                                                <div style="background-color:#ff4b4b; color:white; padding:10px; text-align:center; border-radius:5px; font-family:sans-serif; font-weight:bold;">
                                                    📥 СКАЧАТЬ MP4
                                                </div>
                                            </a>
                                        ''')
                                    else:
                                        st.video(orig)
                                        st.warning("Ссылка без вотермарки не найдена")
                                    st.write(f"🔗 [TikTok Link]({orig})")
                    else: st.warning("Список видео пуст")
                else: st.error("Скрапер еще не запускался")
            except Exception as e:
                st.error(f"Ошибка скрапера: {e}")
