from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import praw
import time

# 1. Настройка мобильного экрана приложения
st.set_page_config(
    page_title="Reddit Spy OSINT",
    page_icon="🕵️‍♂️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Красивое оформление блоков для смартфона
st.markdown("""
    <style>
    .stApp { max-width: 600px; margin: 0 auto; }
    .status-box { padding: 12px; border-radius: 8px; background-color: #f0f2f6; margin-bottom: 10px; border-left: 5px solid #ff4b4b; }
    </style>
""", unsafe_allow_html=True)

# 2. Безопасное подключение к Reddit через секреты хостинга
@st.cache_resource
def init_reddit():
    return praw.Reddit(
        client_id=st.secrets["REDDIT_CLIENT_ID"],
        client_secret=st.secrets["REDDIT_CLIENT_SECRET"],
        user_agent=st.secrets["REDDIT_USER_AGENT"]
    )

try:
    reddit = init_reddit()
except Exception:
    st.error("Ошибка авторизации. Проверьте ключи в настройках Secrets!")

st.title("🕵️‍♂️ Reddit Spy OSINT")
st.caption("Система мобильного мониторинга пользователей")

# 3. Ввод никнейма цели
target_user = st.text_input("Никнейм цели (без u/):", placeholder="spez").strip()

if target_user:
    try:
        user = reddit.redditor(target_user)
        user.id  # Проверка, существует ли юзер

        # Сбор базовых метрик
        reg_date = datetime.fromtimestamp(user.created_utc).strftime('%Y-%m-%d')
        total_karma = user.link_karma + user.comment_karma

        # Плитки с информацией (удобно для пальцев на телефоне)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Общая карма", f"{total_karma:,}")
            st.metric("Карма постов", f"{user.link_karma:,}")
        with col2:
            st.metric("Дата регистрации", reg_date)
            st.metric("Карма комментов", f"{user.comment_karma:,}")

        # Мобильные вкладки меню
        tab1, tab2, tab3 = st.tabs(["📊 Анализ", "📡 Live-Слежка", "👥 Мульти"])

        # --- ВКЛАДКА 1: АНАЛИЗ АКТИВНОСТИ ---
        with tab1:
            st.subheader("Цифровой след")
            subreddits = []
            hours = [0] * 24

            with st.spinner("Сканирую профиль..."):
                for comment in user.comments.new(limit=100):
                    subreddits.append(comment.subreddit.display_name)
                    dt = datetime.fromtimestamp(comment.created_utc)
                    hours[dt.hour] += 1

            if subreddits:
                st.write("**Активность по часам суток:**")
                df_hours = pd.DataFrame({"Час": list(range(24)), "Действия": hours})
                fig = px.bar(df_hours, x="Час", y="Действия", template="plotly_dark")
                fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=200)
                st.plotly_chart(fig, use_container_width=True)

                st.write("**Любимые сабреддиты:**")
                df_subs = pd.DataFrame({"Сабреддит": subreddits}).value_counts().reset_index(name="Кол-во")
                st.dataframe(df_subs.head(5), use_container_width=True)
            else:
                st.info("Нет публичной активности за последнее время.")

        # --- ВКЛАДКА 2: СЛЕДИТЬ В РЕАЛЬНОМ ВРЕМЕНИ ---
        with tab2:
            st.subheader("Режим реального времени")
            run_live = st.checkbox("🔄 Включить активный мониторинг")

            if run_live:
                st.warning("Слежка запущена. Не закрывайте эту страницу.")
                
                if "live_logs" not in st.session_state:
                    st.session_state.live_logs = []
                if "known_ids" not in st.session_state:
                    st.session_state.known_ids = {c.id for c in user.comments.new(limit=10)}

                # Проверяем новые комменты
                for comment in user.comments.new(limit=5):
                    if comment.id not in st.session_state.known_ids:
                        st.session_state.known_ids.add(comment.id)
                        time_now = datetime.now().strftime('%H:%M:%S')
                        log = f"⏱️ *[{time_now}]* **r/{comment.subreddit.display_name}**:<br>{comment.body[:120]}..."
                        st.session_state.live_logs.insert(0, log)

                # Выводим логи (новые сверху)
                for log in st.session_state.live_logs[:10]:
                    st.markdown(f"<div class='status-box'>{log}</div>", unsafe_allow_html=True)

                # Автоматический перезапуск страницы каждые 15 секунд
                countdown = st.empty()
                for i in range(15, 0, -1):
                    countdown.caption(f"Обновление через {i} сек...")
                    time.sleep(1)
                st.rerun()

        # --- ВКЛАДКА 3: ПОИСК ВТОРОГО АККАУНТА ---
        with tab3:
            st.subheader("Анализ мультиаккаунтинга")
            st.write("Поиск людей, общающихся в тех же редких группах, что и цель.")

            if st.button("🔍 Запустить глубокий поиск"):
                with st.spinner("Ищу совпадения в ветках обсуждений..."):
                    target_subs = set(subreddits)
                    ignored_subs = {"askreddit", "funny", "pics", "gaming", "news", "videos", "aww"}
                    rare_target_subs = target_subs - ignored_subs
                    found = False

                    for comment in user.comments.new(limit=3):
                        submission = comment.submission
                        submission.comments.replace_more(limit=0)

                        for reply in submission.comments.list()[:15]:
                            author = reply.author
                            if author and author.name != target_user:
                                susp_subs = {c.subreddit.display_name for c in author.comments.new(limit=15)}
                                matches = rare_target_subs.intersection(susp_subs)

                                if len(matches) >= 2:
                                    st.error(f"⚠️ Подозрение на твинк: **u/{author.name}**")
                                    st.write(f"Совпадения в редких группах: {', '.join(matches)}")
                                    found = True

                    if not found:
                        st.success("Прямых совпадений по редким сообществам не обнаружено.")

    except Exception:
        st.error(f"Пользователь u/{target_user} не найден, забанен или его профиль скрыт.")
