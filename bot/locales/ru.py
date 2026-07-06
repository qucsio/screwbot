TEXTS = {
    "choose_lang": "🌐 Выберите язык / Choose your language:",
    "lang_set": "Язык установлен: Русский 🇷🇺",
    "choose_role": "Кто вы на платформе SCREW PROD?",
    "role_client": "🎧 Клиент",
    "role_creator": "🎨 Исполнитель",
    "ask_nickname": "Введите ваш никнейм в системе:",
    "no_username": (
        "⚠️ У вас не задан @username в Telegram. "
        "Он нужен для связи. Установите его в настройках и нажмите /start заново."
    ),
    "client_registered": (
        "✅ Готово, {nickname}! Вы зарегистрированы как клиент.\n"
        "Открываю главное меню услуг."
    ),
    # Заявка исполнителя
    "creator_ask_service": "Какую услугу вы оказываете? (напр. «Продюсер / биты»)",
    "creator_ask_experience": "Расскажите об опыте (кратко):",
    "creator_ask_portfolio": "Пришлите ссылки на портфолио / соцсети одним сообщением:",
    "creator_application_sent": (
        "✅ Заявка отправлена на модерацию. "
        "Админ свяжется с вами в личных сообщениях."
    ),
    "creator_already_pending": "⏳ Ваша заявка уже на рассмотрении.",
    # Главное меню
    "main_menu": "🎛 Главное меню услуг SCREW PROD:",
    "menu_ready_beats": "🎧 Готовые аранжировки и биты",
    "menu_custom_beats": "🎶 Аранжировки и биты на заказ",
    "menu_mixing": "🎚️ Mixing",
    "menu_ghostwriting": "✍️ Текст (призрак-писатель)",
    "menu_visual": "🖼️ Визуал",
    "menu_videographer": "🎥 Видеограф",
    "menu_editing": "🎬 Монтаж",
    "menu_photo": "📸 Фото-сессия (Москва)",
    "menu_reviews": "💬 Отзывы",
    "back": "⬅️ Назад",
    "wip": "🚧 Раздел в разработке.",
    # Модерация (админу)
    "mod_new_creator": (
        "🆕 <b>Заявка исполнителя</b>\n\n"
        "Контакт: {contact}\n"
        "Ник: {nickname}\n"
        "Услуга: {service}\n"
        "Опыт: {experience}\n"
        "Портфолио: {portfolio}"
    ),
    "mod_approve": "✅ Одобрить",
    "mod_reject": "❌ Отклонить",
    "mod_approved_admin": "Исполнитель одобрен.",
    "mod_rejected_admin": "Заявка отклонена.",
    "creator_approved_notify": "🎉 Ваша заявка одобрена! Добро пожаловать в команду SCREW PROD.",
    "creator_rejected_notify": "К сожалению, ваша заявка отклонена.",
    # --- Загрузка бита ---
    "addbeat_only_creator": "⛔ Добавлять биты могут только одобренные исполнители.",
    "addbeat_title": "🎵 Название бита:",
    "addbeat_genre": "Жанр:",
    "addbeat_key": "Тональность (напр. Am, C#):",
    "addbeat_bpm": "BPM (число):",
    "addbeat_bpm_invalid": "Введите BPM числом (напр. 140).",
    "addbeat_cover": "Пришлите обложку (фото):",
    "addbeat_cover_invalid": "Нужно фото. Пришлите обложку изображением.",
    "addbeat_audio": "Пришлите аудио-сниппет (audio/файл):",
    "addbeat_audio_invalid": "Нужен аудиофайл.",
    "addbeat_price_rent": "💸 Цена аренды (руб.):",
    "addbeat_price_buy": "💰 Цена выкупа (руб.):",
    "addbeat_price_invalid": "Введите цену числом.",
    "addbeat_sent": "✅ Бит отправлен на модерацию.",
    "mod_new_beat": (
        "🆕 <b>Новый бит на модерацию</b>\n\n"
        "Автор: {author}\n"
        "Название: {title}\n"
        "Жанр: {genre} | Тон: {key} | BPM: {bpm}\n"
        "Аренда: {rent} ₽ | Выкуп: {buy} ₽"
    ),
    "beat_approved_notify": "✅ Ваш бит «{title}» одобрен и добавлен в каталог.",
    "beat_rejected_notify": "❌ Ваш бит «{title}» отклонён модерацией.",
    # --- Каталог / фильтр / карусель ---
    "catalog_empty": "😔 В каталоге пока нет одобренных битов.",
    "filter_intro": "🔎 Настройте фильтр или смотрите всё:",
    "filter_all": "▶️ Смотреть все",
    "filter_setup": "🎚 Настроить фильтр",
    "filter_genre": "Выберите жанр:",
    "filter_any": "Любой",
    "filter_key": "Тональность (текстом) или «-» чтобы пропустить:",
    "filter_bpm": "Диапазон BPM в формате «120-140» или «-» чтобы пропустить:",
    "filter_no_results": "😔 Под ваш фильтр ничего не нашлось.",
    "beat_card": (
        "🎵 <b>{title}</b>\n"
        "Автор: {author}\n"
        "Жанр: {genre} | Тон: {key} | BPM: {bpm}\n"
        "💸 Аренда: {rent} ₽ | 💰 Выкуп: {buy} ₽\n"
        "({pos}/{total})"
    ),
    "beat_prev": "⬅️",
    "beat_next": "➡️",
    "beat_listen": "▶️ Слушать",
    "beat_buy": "💸 Купить",
    "beat_ask": "💬 Задать вопрос",
    "beat_ask_prompt": "✍️ Напишите вопрос по биту «{title}» — он уйдёт админу:",
    "beat_ask_sent": "✅ Вопрос отправлен.",
    "beat_buy_sent": "✅ Заявка на покупку отправлена админу, он свяжется с вами.",
    "mod_beat_question": (
        "💬 <b>Вопрос по биту</b> «{title}» (id{work_id})\n"
        "От: {contact}\n\n{text}"
    ),
    "mod_beat_buy": (
        "🛒 <b>Заявка на покупку</b> бита «{title}» (id{work_id})\n"
        "Клиент: {contact}\nАвтор: {author}\n"
        "Аренда: {rent} ₽ | Выкуп: {buy} ₽"
    ),
}
